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


SPLIT_PUNCTUATION = set(".,;:!?ã€‚ï¼Œï¼›ï¼šï¼ï¼Ÿ")
CLOSING_MARKS = set("\"'""'ï¼‰]ã€‹ã€‹>ã€ã€‘")

END_PUNCTUATION = {
    ";",
    ":",
    ",",
    ".",
    "!",
    "?",
    "â€¦",
    ")",
    "]",
    "}",
    '"',
    "'",
    """,
    "'",
    "ï¼›",
    "ï¼š",
    "ï¼Œ",
    "ã€‚",
    "ï¼",
    "ï¼Ÿ",
    "ã€",
    "â€¦â€¦",
    "ï¼‰",
    "ã€‘",
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
    "[laughter]": " haha ",
    "[sigh]": " háº§y... ",
    "[confirmation-en]": " á»« ",
    "[question-en]": " háº£? ",
    "[question-ah]": " Ã¡? ",
    "[question-oh]": " á»“? ",
    "[question-ei]": " Ãª? ",
    "[question-yi]": " Ã½? ",
    "[surprise-ah]": " Ã¡! ",
    "[surprise-oh]": " á»“ ",
    "[surprise-wa]": " Ã²a ",
    "[surprise-yo]": " Ã´i ",
    "[dissatisfaction-hnn]": " há»« ",
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

        text += "ã€‚" if is_chinese else "."

    return text


def normalize_vietnamese_numbers(text: str, is_vi: bool = True) -> str:
    """Normalize Vietnamese decimals (e.g. 372,5 -> 372 pháº©y 5) and thousands separators."""
    import re
    if not text:
        return text

    if not is_vi:
        return text

    # 1. Decimal commas: e.g. 372,5 -> 372 pháº©y 5
    text = re.sub(r'\b(\d+),(\d+)\b', r'\1 pháº©y \2', text)

    # 2. Decimal dots vs thousands separators:
    # If fractional part after dot has exactly 3 digits (like 1.000 or 1.234), it's thousands separator -> remove it.
    # Otherwise (like 372.5 or 1.2), it's a decimal dot -> replace with "pháº©y".
    def replace_dot(match):
        whole = match.group(1)
        fraction = match.group(2)
        if len(fraction) == 3:
            return whole + fraction
        else:
            return whole + " pháº©y " + fraction

    text = re.sub(r'\b(\d+)\.(\d+)\b', replace_dot, text)

    # 3. Clean up remaining thousands dots (e.g. 1.000.000 -> 1000000)
    while True:
        new_text = re.sub(r'\b(\d+)\.(\d{3})\b', r'\1\2', text)
        if new_text == text:
            break
        text = new_text

    # 4. Convert plain numbers to words using num2words if available
    try:
        from num2words import num2words
        def number_to_vietnamese_words(match):
            num_str = match.group(0)
            try:
                if " pháº©y " in num_str:
                    parts = num_str.split(" pháº©y ")
                    whole = num2words(int(parts[0]), lang='vi')
                    # TÃ¡ch tá»«ng sá»‘ tháº­p phÃ¢n Ä‘á»ƒ Ä‘á»c cho tá»± nhiÃªn
                    decimal_digits = " ".join([num2words(int(d), lang='vi') for d in parts[1]])
                    return f"{whole} pháº©y {decimal_digits}"
                else:
                    return num2words(int(num_str), lang='vi')
            except Exception:
                return num_str
        
        # Match standalone numbers or numbers with "pháº©y"
        text = re.sub(r'\b\d+(?: pháº©y \d+)?\b', number_to_vietnamese_words, text)
    except ImportError:
        pass # Fallback to original text if num2words is not installed

    # 5. Thay tháº¿ ngÃ y thÃ¡ng nÄƒm
    def replace_date(match):
        day = match.group(1)
        month = match.group(2)
        year = match.group(3)
        return f" ngÃ y {day} thÃ¡ng {month} nÄƒm {year} "
    
    text = re.sub(r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b', replace_date, text)

    # 6. Thay tháº¿ giá» phÃºt
    def replace_time(match):
        hour = match.group(1)
        minute = match.group(2)
        return f" {hour} giá» {minute} phÃºt "
    
    text = re.sub(r'\b(\d{1,2}):(\d{2})\b', replace_time, text)

    # 7. Thay tháº¿ %
    text = re.sub(r'(\d+)%', r'\1 pháº§n trÄƒm', text)
    
    # 8. Thay tháº¿ cÃ¡c Ä‘Æ¡n vá»‹ tiá»n tá»‡/Ä‘o lÆ°á»ng cÆ¡ báº£n (Ä‘á»ƒ trÃ¡nh bá»‹ Ä‘á»c nuá»‘t)
    text = re.sub(r'\b(\d+)\s*k\b', r'\1 nghÃ¬n', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*tr\b', r'\1 triá»‡u', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*Ä‘\b', r'\1 Ä‘á»“ng', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*vnd\b', r'\1 viá»‡t nam Ä‘á»“ng', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*km\b', r'\1 ki lÃ´ mÃ©t', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*kg\b', r'\1 ki lÃ´ gam', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*m\b', r'\1 mÃ©t', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(\d+)\s*cm\b', r'\1 xÄƒng ti mÃ©t', text, flags=re.IGNORECASE)

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
    text = re.sub(r'\b(ha\s*){2,}\b', ' haha ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(he\s*){2,}\b', ' hÃ© hÃ© hÃ© ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(hi\s*){2,}\b', ' hÃ­ hÃ­ hÃ­ ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(hÃ´\s*){2,}\b', ' há»‘ há»‘ há»‘ ', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(ho\s*){2,}\b', ' hÃ´ hÃ´ hÃ´ ', text, flags=re.IGNORECASE)

    # Sighs: haizz, thá»Ÿ dÃ i
    text = re.sub(r'\bhaiz+\b', ' háº§y... ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bthá»Ÿ dÃ i\b', ' háº§y... ', text, flags=re.IGNORECASE)

    # Dissatisfaction: há»«m, hmm
    text = re.sub(r'\bh[Æ°á»«]m+\b', ' há»« ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bhm+\b', ' há»« ', text, flags=re.IGNORECASE)

    # Surprise cues without overriding existing question punctuation.
    text = re.sub(r'\b[u]?[oÃ²]Ã (?!!|\?)\b', ' Ã²a ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bá»“+(?!!|\?)\b', ' á»“ ', text, flags=re.IGNORECASE)
    text = re.sub(r'\bÃ¡+(?!!|\?)\b', ' Ã¡! ', text, flags=re.IGNORECASE)

    text = re.sub(r'\s+', ' ', text)
    return text.strip()
