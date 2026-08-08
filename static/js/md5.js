/* CManager 统一客户端 MD5 计算（RFC 1321 增量实现）。
 *
 * 用途：文件去重要求 MD5 全部在用户浏览器内计算，服务器只接收
 * 客户端提交的 32 位小写十六进制 MD5，不自行读取文件内容做校验。
 *
 * 暴露：
 *   window.CManagerMD5.hashBytes(bytes)        -> hex 字符串（同步）
 *   window.CManagerMD5.hashFile(file, onProgress) -> Promise<hex>（分块增量）
 */
(function () {
    'use strict';

    // 无符号 32 位安全加法（避免 JS 有符号溢出）
    function safeAdd(x, y) {
        var lsw = (x & 0xffff) + (y & 0xffff);
        var msw = (x >> 16) + (y >> 16) + (lsw >> 16);
        return (msw << 16) | (lsw & 0xffff);
    }

    function bitRotateLeft(num, cnt) {
        return (num << cnt) | (num >>> (32 - cnt));
    }

    function md5cmn(q, a, b, x, s, t) {
        return safeAdd(bitRotateLeft(safeAdd(safeAdd(a, q), safeAdd(x, t)), s), b);
    }

    function md5ff(a, b, c, d, x, s, t) {
        return md5cmn((b & c) | (~b & d), a, b, x, s, t);
    }

    function md5gg(a, b, c, d, x, s, t) {
        return md5cmn((b & d) | (c & ~d), a, b, x, s, t);
    }

    function md5hh(a, b, c, d, x, s, t) {
        return md5cmn(b ^ c ^ d, a, b, x, s, t);
    }

    function md5ii(a, b, c, d, x, s, t) {
        return md5cmn(c ^ (b | ~d), a, b, x, s, t);
    }

    var S = [
        7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22, 7, 12, 17, 22,
        5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20, 5, 9, 14, 20,
        4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23, 4, 11, 16, 23,
        6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21, 6, 10, 15, 21
    ];

    // T[i] = floor(2^32 * abs(sin(i)))，i 从 1 到 64
    var T = [];
    for (var tIndex = 1; tIndex <= 64; tIndex++) {
        var raw = Math.abs(Math.sin(tIndex)) * 0x100000000;
        T.push(Math.floor(raw) >>> 0);
    }

    function processBlock(state, block) {
        var M = [];
        for (var i = 0; i < 64; i += 4) {
            M[i >> 2] =
                (block[i] | (block[i + 1] << 8) | (block[i + 2] << 16) | (block[i + 3] << 24)) >>> 0;
        }
        var a = state[0], b = state[1], c = state[2], d = state[3];
        for (var j = 0; j < 64; j++) {
            var round = j >> 4;
            var f;
            var g;
            if (round === 0) {
                f = (b & c) | (~b & d);
                g = j;
            } else if (round === 1) {
                f = (b & d) | (c & ~d);
                g = (5 * j + 1) % 16;
            } else if (round === 2) {
                f = b ^ c ^ d;
                g = (3 * j + 5) % 16;
            } else {
                f = c ^ (b | ~d);
                g = (7 * j) % 16;
            }
            f = safeAdd(safeAdd(a, f), safeAdd(M[g], T[j]));
            f = bitRotateLeft(f, S[j]);
            a = d;
            d = c;
            c = b;
            b = safeAdd(b, f);
        }
        state[0] = safeAdd(state[0], a);
        state[1] = safeAdd(state[1], b);
        state[2] = safeAdd(state[2], c);
        state[3] = safeAdd(state[3], d);
    }

    function Md5Hasher() {
        this.state = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476];
        this.buffer = new Uint8Array(64);
        this.bufferLength = 0;
        this.totalLength = 0; // 字节数（用于 64 位长度填充的低 32 位）
    }

    Md5Hasher.prototype.update = function (bytes) {
        var data = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
        this.totalLength = (this.totalLength + data.length) >>> 0;
        var offset = 0;
        if (this.bufferLength > 0) {
            var need = 64 - this.bufferLength;
            var copy = Math.min(need, data.length);
            this.buffer.set(data.subarray(0, copy), this.bufferLength);
            this.bufferLength += copy;
            offset += copy;
            if (this.bufferLength === 64) {
                processBlock(this.state, this.buffer);
                this.bufferLength = 0;
            }
        }
        while (offset + 64 <= data.length) {
            processBlock(this.state, data.subarray(offset, offset + 64));
            offset += 64;
        }
        if (offset < data.length) {
            var rest = data.length - offset;
            this.buffer.set(data.subarray(offset), 0);
            this.bufferLength = rest;
        }
    };

    Md5Hasher.prototype.digest = function () {
        var bitLengthLow = (this.totalLength * 8) >>> 0;
        var bitLengthHigh = Math.floor(this.totalLength / 0x20000000) >>> 0;
        var tail = new Uint8Array(128);
        tail[0] = 0x80;
        var used = this.bufferLength;
        // 64 字节块内 padding：总长 mod 64 == 56 时需要一个额外的 64 字节块
        var paddingNeeded = used < 56 ? 56 - used : 120 - used;
        this.update(tail.subarray(0, paddingNeeded));
        var lengthTail = new Uint8Array(8);
        lengthTail[0] = bitLengthLow & 0xff;
        lengthTail[1] = (bitLengthLow >>> 8) & 0xff;
        lengthTail[2] = (bitLengthLow >>> 16) & 0xff;
        lengthTail[3] = (bitLengthLow >>> 24) & 0xff;
        lengthTail[4] = bitLengthHigh & 0xff;
        lengthTail[5] = (bitLengthHigh >>> 8) & 0xff;
        lengthTail[6] = (bitLengthHigh >>> 16) & 0xff;
        lengthTail[7] = (bitLengthHigh >>> 24) & 0xff;
        this.update(lengthTail);

        var hex = '';
        for (var i = 0; i < 4; i++) {
            var word = this.state[i] >>> 0;
            for (var byteIndex = 0; byteIndex < 4; byteIndex++) {
                var byteValue = (word >>> (byteIndex * 8)) & 0xff;
                hex += (byteValue < 16 ? '0' : '') + byteValue.toString(16);
            }
        }
        return hex;
    };

    function hashBytes(bytes) {
        var hasher = new Md5Hasher();
        hasher.update(bytes);
        return hasher.digest();
    }

    function hashFile(file, onProgress) {
        return new Promise(function (resolve, reject) {
            if (!file || typeof file.slice !== 'function') {
                reject(new Error(gettext('无法读取文件内容')));
                return;
            }
            var chunkSize = 2 * 1024 * 1024;
            var total = file.size || 0;
            var read = 0;
            var hasher = new Md5Hasher();
            var reader = new FileReader();

            function nextChunk() {
                if (read >= total) {
                    resolve(hasher.digest());
                    return;
                }
                var slice = file.slice(read, Math.min(read + chunkSize, total));
                reader.onload = function () {
                    if (!reader.result) {
                        reject(new Error(gettext('读取文件失败')));
                        return;
                    }
                    hasher.update(new Uint8Array(reader.result));
                    read += slice.size;
                    if (typeof onProgress === 'function' && total > 0) {
                        onProgress(Math.min(1, read / total));
                    }
                    nextChunk();
                };
                reader.onerror = function () {
                    reject(new Error(gettext('读取文件失败，请重试')));
                };
                reader.readAsArrayBuffer(slice);
            }
            nextChunk();
        });
    }

    window.CManagerMD5 = {
        hashBytes: hashBytes,
        hashFile: hashFile
    };

    // 自检：防止缓存了损坏或错误的实现（不依赖 TextEncoder，兼容旧浏览器）
    function asciiBytes(text) {
        var out = new Uint8Array(text.length);
        for (var i = 0; i < text.length; i++) {
            out[i] = text.charCodeAt(i) & 0xff;
        }
        return out;
    }
    if (hashBytes(new Uint8Array(0)) !== 'd41d8cd98f00b204e9800998ecf8427e' ||
        hashBytes(asciiBytes('abc')) !== '900150983cd24fb0d6963f7d28e17f72') {
        // eslint-disable-next-line no-console
        console.error(gettext('[CManager] MD5 自检失败，文件去重将不可用'));
    }
})();
