"""UAPI 自动翻译服务相关测试。"""

from unittest.mock import patch

import requests

from django.test import TestCase

from ..models import SiteSettings
from ..services.object_translations import (
    TRANSLATION_LANGUAGES,
    save_object_translations,
    translate_text,
)


class FakeResponse:
    """最小可用的 requests.Response 替身。"""

    def __init__(self, payload, ok=True, status_code=200):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f'{self.status_code} error')


class TranslateTextTests(TestCase):
    def setUp(self):
        self.cfg = SiteSettings.get_settings()
        self.cfg.auto_translate_enabled = True
        self.cfg.save(update_fields=['auto_translate_enabled'])

    def test_standard_endpoint_used_first(self):
        standard = FakeResponse({'text': '你好', 'translate': 'Hello'})
        with patch('requests.post', return_value=standard) as mocked:
            result = translate_text('你好', 'en')
        self.assertEqual(result, 'Hello')
        self.assertEqual(mocked.call_count, 1)
        args, kwargs = mocked.call_args
        self.assertTrue(args[0].endswith('/api/v1/translate/text'))
        self.assertEqual(kwargs['params'], {'to_lang': 'en'})

    def test_falls_back_to_ai_endpoint_when_standard_fails(self):
        standard = FakeResponse({'error': '翻译服务暂时不可用'}, ok=False, status_code=500)
        ai = FakeResponse({
            'message': 'Translation completed successfully',
            'data': {'translated_text': 'Клубын жилийн шалгалтын өргөдөл'},
        })
        with patch('requests.post', side_effect=[standard, ai]) as mocked:
            result = translate_text('社团年审申请', 'mn')
        self.assertEqual(result, 'Клубын жилийн шалгалтын өргөдөл')
        self.assertEqual(mocked.call_count, 2)
        _, ai_kwargs = mocked.call_args_list[1]
        self.assertTrue(ai_kwargs['json']['target_lang'] == 'mn')
        self.assertEqual(ai_kwargs['json']['text'], '社团年审申请')

    def test_falls_back_to_ai_endpoint_when_standard_response_invalid(self):
        standard = FakeResponse({'text': '社团年审申请'}, ok=True)
        ai = FakeResponse({
            'data': {'translated_text': 'تىمەر يىللىق تەستىقىلاش ئىلتىماسى'},
        })
        with patch('requests.post', side_effect=[standard, ai]):
            result = translate_text('社团年审申请', 'ug')
        self.assertEqual(result, 'تىمەر يىللىق تەستىقىلاش ئىلتىماسى')

    def test_raises_when_both_endpoints_fail(self):
        standard = FakeResponse({'error': 'down'}, ok=False, status_code=500)
        ai = FakeResponse({'error': 'down'}, ok=False, status_code=429)
        with patch('requests.post', side_effect=[standard, ai]):
            with self.assertRaises(requests.HTTPError):
                translate_text('社团年审申请', 'ug')

    def test_auto_translate_failure_does_not_block_saving(self):
        standard = FakeResponse({'error': 'down'}, ok=False, status_code=500)
        ai = FakeResponse({'error': 'down'}, ok=False, status_code=429)
        from ..models import FormChannel
        channel = FormChannel.objects.create(
            name='测试通道',
            slug='translate-test',
            builtin_action='none',
        )
        with patch('requests.post', side_effect=[standard, ai] * len(TRANSLATION_LANGUAGES)):
            # 不应抛异常，译文保持为空即可
            save_object_translations(
                channel,
                translations={'name': {}},
                auto_translate=True,
                source_texts={'name': '测试通道'},
            )
        self.assertTrue(channel.pk)
