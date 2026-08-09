"""对象内容多语言翻译：存储、读取与 UAPI 翻译服务自动翻译。"""

import json
import logging
from functools import lru_cache

from django.utils.translation import get_language

from ..models import ObjectTranslation, SiteSettings

logger = logging.getLogger(__name__)


# 全站支持的语言（与 settings.LANGUAGES 保持一致）。zh-hans 是源语言，
# 不进入译文表；其余语言均可由 UAPI 翻译服务自动生成。
SOURCE_LANGUAGE = 'zh-hans'
TRANSLATION_LANGUAGES = ('en', 'ug', 'mn')


def current_language():
    """返回当前激活语言，源语言与未支持语言统一归一化为 zh-hans。"""
    lang = get_language() or SOURCE_LANGUAGE
    return lang if lang in TRANSLATION_LANGUAGES else SOURCE_LANGUAGE


def translated_text(obj, field_name, languages=None, fallback=''):
    """单条译文读取；没有译文时返回 fallback。"""
    if obj is None or not getattr(obj, 'pk', None):
        return fallback
    lang = current_language()
    if lang not in (languages or TRANSLATION_LANGUAGES):
        return fallback
    row = _cached_translation(obj._meta.model_name, obj.pk, field_name, lang)
    if row is None:
        return fallback
    return row


@lru_cache(maxsize=2048)
def _cached_translation(object_type, object_id, field_name, language):
    """进程内译文缓存；保存/删除译文时调用 cache_clear() 失效。"""
    try:
        return ObjectTranslation.objects.filter(
            object_type=object_type,
            object_id=object_id,
            field_name=field_name,
            language=language,
        ).values_list('text', flat=True).first()
    except Exception:
        return None


def _clear_translation_cache():
    _cached_translation.cache_clear()


def save_object_translations(obj, translations, auto_translate=False, source_texts=None):
    """写入/删除对象译文。

    translations: {field_name: {language: text}}，值为空字符串的条目会删除
    已有译文。auto_translate=True 时，对 source_texts 中每个字段对应的源文案，
    为尚未提供译文的语言调用 UAPI 翻译服务补齐，失败时静默降级。
    """
    if obj is None or not getattr(obj, 'pk', None):
        return
    object_type = obj._meta.model_name
    source_texts = source_texts or {}
    for field_name, lang_texts in (translations or {}).items():
        for language, text in (lang_texts or {}).items():
            if language not in TRANSLATION_LANGUAGES:
                continue
            text = (text or '').strip()
            if text:
                _upsert_translation(object_type, obj.pk, field_name, language, text)
            else:
                ObjectTranslation.objects.filter(
                    object_type=object_type,
                    object_id=obj.pk,
                    field_name=field_name,
                    language=language,
                ).delete()
    _clear_translation_cache()
    if not auto_translate:
        return
    existing = set(ObjectTranslation.objects.filter(
        object_type=object_type,
        object_id=obj.pk,
        field_name__in=translations.keys(),
    ).values_list('field_name', 'language'))
    for field_name, lang_texts in (translations or {}).items():
        source_text = (source_texts.get(field_name) or '').strip()
        if not source_text:
            continue
        for language in TRANSLATION_LANGUAGES:
            provided = (lang_texts or {}).get(language, '').strip()
            if provided or (field_name, language) in existing:
                continue
            try:
                text = translate_text(source_text, language)
            except Exception as exc:  # 外部服务失败不允许阻塞保存
                logger.warning('auto translate failed (%s): %s', language, exc)
                continue
            if text:
                _upsert_translation(object_type, obj.pk, field_name, language, text, auto=True)
    _clear_translation_cache()


def _upsert_translation(object_type, object_id, field_name, language, text, auto=False):
    ObjectTranslation.objects.update_or_create(
        object_type=object_type,
        object_id=object_id,
        field_name=field_name,
        language=language,
        defaults={'text': text, 'auto_translated': auto},
    )


def parse_options_translation(raw):
    """把选项译文表单值解析为 JSON 列表。"""
    if not raw:
        return []
    raw = raw.strip()
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return [str(item) for item in value]
    except (TypeError, ValueError):
        pass
    return [line.strip() for line in raw.splitlines() if line.strip()]


def translate_text(source, target):
    """调用 UAPI 翻译服务（https://uapis.cn）翻译单段文本。

    优先调用普通翻译接口：POST /api/v1/translate/text?to_lang=<目标语言>，
    body 为 {"text": ...}，响应 {"translate": ..., "text": ...}。该接口对
    部分语言（如蒙古语 mn、维吾尔语 ug）会返回 500，此时自动回退到 AI 智能
    翻译接口：POST /api/v1/ai/translate，body 为 {"target_lang": ..., "text":
    ...}，响应 {"data": {"translated_text": ...}}。源语言自动检测。两个接口
    均失败时抛异常，由调用方静默降级处理。
    """
    import requests

    cfg = SiteSettings.get_settings()
    endpoint = (cfg.translation_api_base_url or 'https://uapis.cn').strip().rstrip('/')
    headers = {'Content-Type': 'application/json'}
    api_key = (cfg.translation_api_key or '').strip()
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    # 1) 普通翻译接口
    try:
        response = requests.post(
            f'{endpoint}/api/v1/translate/text',
            params={'to_lang': target},
            json={'text': source},
            headers=headers,
            timeout=15,
        )
        data = response.json()
        if response.ok and isinstance(data, dict) and data.get('translate'):
            return str(data['translate']).strip()
    except (requests.RequestException, ValueError):
        pass

    # 2) AI 智能翻译接口（普通接口不支持的语言回退到这里）
    response = requests.post(
        f'{endpoint}/api/v1/ai/translate',
        json={'target_lang': target, 'text': source},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    translated = None
    if isinstance(data, dict):
        payload = data.get('data')
        if isinstance(payload, dict):
            translated = payload.get('translated_text')
    if not translated:
        raise ValueError(f'翻译服务返回了无效响应: {data!r}')
    return str(translated).strip()
