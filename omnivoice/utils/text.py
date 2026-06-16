#!/usr/bin/env python3
# Copyright    2026  Xiaomi Corp.        (authors:  Han Zhu)
#
# See ../../LICENSE for clarification regarding multiple authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Text processing utilities for TTS inference.

Provides:
- ``chunk_text_punctuation()``: Splits long text into model-friendly chunks at
  sentence boundaries, with abbreviation-aware punctuation splitting.
- ``add_punctuation()``: Appends missing end punctuation (Chinese or English).
"""

import re
from typing import List, Optional

from omnivoice.utils.vi_sensitive_terms import VI_PRONUNCIATION_SENSITIVE_TERMS


SPLIT_PUNCTUATION = set(".,;:!?。，；：！？")
CLOSING_MARKS = set("\"'""'）]》》>ã€」")

END_PUNCTUATION = {
    ";",
    ":",
    ",",
    ".",
    "!",
    "?",
    "…",
    ")",
    "]",
    "}",
    '"',
    "'",
    """,
    "'",
    "；",
    "：",
    "，",
    "。",
    "！",
    "？",
    "』",
    "……",
    "）",
    "」",
    """,
    "'",
}


ABBREVIATIONS = {
    "Mr.",
    "Mrs.",
    "Ms.",
    "Dr.",
    "Prof.",
    "Sr.",
    "Jr.",
    "Rev.",
    "Fr.",
    "Hon.",
    "Pres.",
    "Gov.",
    "Capt.",
    "Gen.",
    "Sen.",
    "Rep.",
    "Col.",
    "Maj.",
    "Lt.",
    "Cmdr.",
    "Sgt.",
    "Cpl.",
    "Co.",
    "Corp.",
    "Inc.",
    "Ltd.",
    "Est.",
    "Dept.",
    "St.",
    "Ave.",
    "Blvd.",
    "Rd.",
    "Mt.",
    "Ft.",
    "No.",
    "Jan.",
    "Feb.",
    "Mar.",
    "Apr.",
    "Aug.",
    "Sep.",
    "Sept.",
    "Oct.",
    "Nov.",
    "Dec.",
    "i.e.",
    "e.g.",
    "vs.",
    "Vs.",
    "Etc.",
    "approx.",
    "fig.",
    "def.",
}


_SENSITIVE_END_RE = re.compile(
    r"(?iu)(?:^|\s)(" + "|".join(
        sorted((re.escape(term) for term in VI_PRONUNCIATION_SENSITIVE_TERMS), key=len, reverse=True)
    ) + r")\W*$"
)


VI_NONVERBAL_TAG_FALLBACKS = {
    "[laughter]": " hahaha ",
    "[sigh]": " thở dài ",
    "[confirmation-en]": " ừm ",
    "[question-en]": " hử? ",
    "[question-ah]": " á? ",
    "[question-oh]": " ồ? ",
    "[question-ei]": " ê? ",
    "[question-yi]": " ý? ",
    "[surprise-ah]": " á! ",
    "[surprise-oh]": " ồ! ",
    "[surprise-wa]": " oa! ",
    "[surprise-yo]": " ôi! ",
    "[dissatisfaction-hnn]": " hừm ",
}

_SUPPORTED_NONVERBAL_TAGS_PATTERN = "|".join(
    sorted((re.escape(tag) for tag in VI_NONVERBAL_TAG_FALLBACKS), key=len, reverse=True)
)
_EXACT_REPEATED_NONVERBAL_RE = re.compile(
    rf"(?i)(?P<tag>{_SUPPORTED_NONVERBAL_TAGS_PATTERN})(?:\s+(?P=tag))+"
)
_ADJACENT_SURPRISE_RE = re.compile(
    r"(?i)(?:\[(?:surprise-ah|surprise-oh|surprise-wa|surprise-yo)\])"
    r"(?:\s+\[(?:surprise-ah|surprise-oh|surprise-wa|surprise-yo)\])+"
)


def ends_with_sensitive_vietnamese_term(text: str) -> bool:
    text = text.strip()
    if not text:
        return False
    return _SENSITIVE_END_RE.search(text) is not None


def collapse_adjacent_nonverbal_tags(text: str) -> str:
    """Collapse repeated adjacent supported non-verbal tags across whitespace only."""
    if not text:
        return text

    text = _EXACT_REPEATED_NONVERBAL_RE.sub(lambda match: match.group("tag"), text)
    text = _ADJACENT_SURPRISE_RE.sub("[surprise-oh]", text)
    return text


def chunk_text_punctuation(
    text: str,
    chunk_len: int,
    min_chunk_len: Optional[int] = None,
) -> List[str]:
    """
    Splits the input tokens list into chunks according to punctuations,
    avoiding splits on common abbreviations (e.g., Mr., No.).
    """

    # 1. Split the tokens according to punctuations.
    sentences = []
    current_sentence = []

    tokens_list = list(text)

    for token in tokens_list:
        # If the first token of current sentence is punctuation,
        # append it to the end of the previous sentence.
        if (
            len(current_sentence) == 0
            and len(sentences) != 0
            and (token in SPLIT_PUNCTUATION or token in CLOSING_MARKS)
        ):
            sentences[-1].append(token)
        # Otherwise, append the current token to the current sentence.
        else:
            current_sentence.append(token)

            # Split the sentence in positions of punctuations.
            if token in SPLIT_PUNCTUATION:
                is_abbreviation = False

                if token == ".":
                    temp_str = "".join(current_sentence).strip()
                    if temp_str:
                        last_word = temp_str.split()[-1]
                        if last_word in ABBREVIATIONS:
                            is_abbreviation = True

                if not is_abbreviation:
                    sentences.append(current_sentence)
                    current_sentence = []
    # Assume the last few tokens are also a sentence
    if len(current_sentence) != 0:
        sentences.append(current_sentence)

    # 2. Merge short sentences.
    merged_chunks = []
    current_chunk = []
    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= chunk_len:
            current_chunk.extend(sentence)
        else:
            if len(current_chunk) > 0:
                merged_chunks.append(current_chunk)
            current_chunk = sentence

    if len(current_chunk) > 0:
        merged_chunks.append(current_chunk)

    # 4. Post-process: Check for undersized chunks and merge them
    #  with the previous chunk or next chunk (if it's the first chunk).
    if min_chunk_len is not None:
        first_chunk_short_flag = (
            len(merged_chunks) > 0 and len(merged_chunks[0]) < min_chunk_len
        )
        final_chunks = []
        for i, chunk in enumerate(merged_chunks):
            if i == 1 and first_chunk_short_flag:
                final_chunks[-1].extend(chunk)
            else:
                if len(chunk) >= min_chunk_len:
                    final_chunks.append(chunk)
                else:
                    if len(final_chunks) == 0:
                        final_chunks.append(chunk)
                    else:
                        final_chunks[-1].extend(chunk)
    else:
        final_chunks = merged_chunks

    chunk_strings = [
        "".join(chunk).strip() for chunk in final_chunks if "".join(chunk).strip()
    ]
    return chunk_strings


def add_punctuation(text: str):
    """Add punctuation if there is not in the end of text"""
    text = text.strip()

    if not text:
        return text

    if text[-1] not in END_PUNCTUATION:
        is_chinese = any("\u4e00" <= char <= "\u9fff" for char in text)

        text += "。" if is_chinese else "."

    return text


def normalize_vietnamese_numbers(text: str, is_vi: bool = True) -> str:
    """Normalize Vietnamese decimals (e.g. 372,5 -> 372 phẩy 5) and thousands separators."""
    import re
    if not text or not is_vi:
        return text

    # ── Bộ chuyển số → chữ tiếng Việt (built-in, không cần num2words) ──────
    _DON_VI    = ['', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']
    _HANG_CHUC = ['', 'mười', 'hai mươi', 'ba mươi', 'bốn mươi', 'năm mươi',
                  'sáu mươi', 'bảy mươi', 'tám mươi', 'chín mươi']

    def _doc_nhom(nhom: int) -> str:
        if nhom == 0:
            return ''
        tram = nhom // 100
        chuc = (nhom % 100) // 10
        dv   = nhom % 10
        res  = ''
        if tram > 0:
            res += _DON_VI[tram] + ' trăm'
        if chuc == 0 and dv > 0 and tram > 0:
            res += ' lẻ ' + _DON_VI[dv]
        elif chuc == 1:
            res += ' mười'
            if dv == 5:   res += ' lăm'
            elif dv > 0:  res += ' ' + _DON_VI[dv]
        elif chuc > 1:
            res += ' ' + _HANG_CHUC[chuc]
            if dv == 5:   res += ' lăm'
            elif dv == 1: res += ' mốt'
            elif dv > 0:  res += ' ' + _DON_VI[dv]
        elif chuc == 0 and dv > 0 and tram == 0:
            res += _DON_VI[dv]
        return res.strip()

    def _so_ra_chu(n: int) -> str:
        if n == 0:
            return 'không'
        res     = ''
        ty      = n // 1_000_000_000
        trieu   = (n % 1_000_000_000) // 1_000_000
        nghin   = (n % 1_000_000) // 1_000
        con_lai = n % 1_000
        if ty > 0:
            res += _doc_nhom(ty) + ' tỷ'
        if trieu > 0:
            if res: res += ' '
            res += _doc_nhom(trieu) + ' triệu'
        if nghin > 0:
            if res: res += ' '
            res += _doc_nhom(nghin) + ' nghìn'
        if con_lai > 0:
            if res: res += ' '
            res += _doc_nhom(con_lai)
        return res.strip()
    # ─────────────────────────────────────────────────────────────────────────

    # 1. Ngày/tháng/năm: 12/06/2026 → ngày mười hai tháng sáu năm hai nghìn không trăm hai mươi sáu
    def _replace_date(m):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f" ngày {_so_ra_chu(d)} tháng {_so_ra_chu(mo)} năm {_so_ra_chu(y)} "
    text = re.sub(r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b', _replace_date, text)

    # 2. Giờ:phút: 14:30 → mười bốn giờ ba mươi phút
    def _replace_time(m):
        h, mn = int(m.group(1)), int(m.group(2))
        return f" {_so_ra_chu(h)} giờ {_so_ra_chu(mn)} phút "
    text = re.sub(r'\b(\d{1,2}):(\d{2})\b', _replace_time, text)

    # 3. Phần trăm: 30% → ba mươi phần trăm
    text = re.sub(r'(\d+)%', lambda m: _so_ra_chu(int(m.group(1))) + ' phần trăm', text)

    # 4. Đơn vị tiền/đo lường dính sát số
    text = re.sub(r'\b(\d+)\s*k\b',   lambda m: _so_ra_chu(int(m.group(1))) + ' nghìn',          text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*tr\b',  lambda m: _so_ra_chu(int(m.group(1))) + ' triệu',          text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*đ\b',   lambda m: _so_ra_chu(int(m.group(1))) + ' đồng',           text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*vnd\b', lambda m: _so_ra_chu(int(m.group(1))) + ' việt nam đồng',  text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*km\b',  lambda m: _so_ra_chu(int(m.group(1))) + ' ki lô mét',      text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*kg\b',  lambda m: _so_ra_chu(int(m.group(1))) + ' ki lô gam',      text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*cm\b',  lambda m: _so_ra_chu(int(m.group(1))) + ' xăng ti mét',    text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*m\b',   lambda m: _so_ra_chu(int(m.group(1))) + ' mét',             text, flags=re.IGNORECASE)

    # 5. Số thập phân dấu phẩy: 372,5 → ba trăm bảy mươi hai phẩy năm
    def _replace_decimal_comma(m):
        whole      = _so_ra_chu(int(m.group(1)))
        dec_digits = ' '.join([_DON_VI[int(d)] if d != '0' else 'không' for d in m.group(2)])
        return f"{whole} phẩy {dec_digits}"
    text = re.sub(r'\b(\d+),(\d{1,2})\b', _replace_decimal_comma, text)

    # 6. Số thập phân dấu chấm (không phải phân cách nghìn): 372.5 → phẩy năm
    def _replace_dot(m):
        whole    = m.group(1)
        fraction = m.group(2)
        if len(fraction) == 3:
            return whole + fraction   # phân cách nghìn → gộp lại
        dec_digits = ' '.join([_DON_VI[int(d)] if d != '0' else 'không' for d in fraction])
        return _so_ra_chu(int(whole)) + ' phẩy ' + dec_digits
    text = re.sub(r'\b(\d+)\.(\d+)\b', _replace_dot, text)

    # 7. Dọn dấu chấm phân cách nghìn còn sót
    while True:
        new_text = re.sub(r'\b(\d+)\.(\d{3})\b', r'\1\2', text)
        if new_text == text:
            break
        text = new_text

    # 8. Số có dấu phẩy phân cách nghìn: 1,000,000 → một triệu
    def _replace_comma_sep(m):
        clean = m.group(0).replace(',', '')
        try:
            return _so_ra_chu(int(clean))
        except Exception:
            return m.group(0)
    text = re.sub(r'\b\d{1,3}(?:,\d{3})+\b', _replace_comma_sep, text)

    # 9. Số nguyên còn lại
    text = re.sub(r'\b\d+\b', lambda m: _so_ra_chu(int(m.group(0))), text)

    return text.strip()


def map_vietnamese_emotions(text: str) -> str:
    """Map common Vietnamese emotion words to safe vocalized cues.

    The local OmniVoice tokenizer in this project does not treat tags like
    ``[laughter]`` as special atomic tokens, so if we keep them literal the
    model may read the bracketed text out loud. We therefore convert both
    colloquial emotion words and explicit tags into speech-friendly cues.
    """
    import re
    if not text:
        return text

    text = collapse_adjacent_nonverbal_tags(text)

    for tag, replacement in VI_NONVERBAL_TAG_FALLBACKS.items():
        text = re.sub(re.escape(tag), replacement, text, flags=re.IGNORECASE)

    # Laughter: haha, hahaha, hehe, hihi, hoho, ha ha, he he
    text = re.sub(r'\b(ha\s*){2,}\b', ' hahaha ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(he\s*){2,}\b', ' he he he ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(hi\s*){2,}\b', ' hi hi hi ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(hô\s*){2,}\b', ' hô hô hô ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(ho\s*){2,}\b', ' hô hô hô ', text, flags=re.IGNORECASE)

    # Sighs: haizz, thở dài
    text = re.sub(r'\bhaiz+\b', ' haizz... ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bthở dài\b', ' haizz... ', text, flags=re.IGNORECASE)

    # Dissatisfaction: hừm, hmm
    text = re.sub(r'\bh[ưừ]m+\b', ' hừm ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bhm+\b', ' hừm ', text, flags=re.IGNORECASE)

    # Surprise cues without overriding existing question punctuation.
    text = re.sub(r'\b[u]?[oò]a(?!!|\?)\b', ' oa! ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bồ+(?!!|\?)\b', ' ồ! ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bá+(?!!|\?)\b', ' á! ', text, flags=re.IGNORECASE)

    text = re.sub(r'(haizz\.\.\.)\s*(?:\.\.\.)+', r'\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
