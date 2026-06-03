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

from typing import List, Optional


SPLIT_PUNCTUATION = set(".,;:!?。，；：！？")
CLOSING_MARKS = set("\"'""'）]》》>」】")

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
    "、",
    "……",
    "）",
    "】",
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
    if not text:
        return text

    if not is_vi:
        return text

    # 1. Decimal commas: e.g. 372,5 -> 372 phẩy 5
    text = re.sub(r'\b(\d+),(\d+)\b', r'\1 phẩy \2', text)

    # 2. Decimal dots vs thousands separators:
    # If fractional part after dot has exactly 3 digits (like 1.000 or 1.234), it's thousands separator -> remove it.
    # Otherwise (like 372.5 or 1.2), it's a decimal dot -> replace with "phẩy".
    def replace_dot(match):
        whole = match.group(1)
        fraction = match.group(2)
        if len(fraction) == 3:
            return whole + fraction
        else:
            return whole + " phẩy " + fraction

    text = re.sub(r'\b(\d+)\.(\d+)\b', replace_dot, text)

    # 3. Clean up remaining thousands dots (e.g. 1.000.000 -> 1000000)
    while True:
        new_text = re.sub(r'\b(\d+)\.(\d{3})\b', r'\1\2', text)
        if new_text == text:
            break
        text = new_text

    return text


def map_vietnamese_emotions(text: str) -> str:
    """Map common Vietnamese emotion words to OmniVoice non-verbal tags."""
    import re
    if not text:
        return text
    
    # Laughter: haha, hahaha, hehe, hihi, hoho, ha ha, he he
    text = re.sub(r'\b(ha\s*){2,}\b', 'há há há', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(he\s*){2,}\b', 'hé hé hé', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(hi\s*){2,}\b', 'hí hí hí', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(hô\s*){2,}\b', 'hố hố hố', text, flags=re.IGNORECASE)
    
    # Sighs: haizz, thở dài
    text = re.sub(r'\bhaiz+\b', '[sigh]', text, flags=re.IGNORECASE)
    text = re.sub(r'\bthở dài\b', '[sigh]', text, flags=re.IGNORECASE)
    
    # Dissatisfaction: hừm, hmm
    text = re.sub(r'\bh[ưừ]m+\b', '[dissatisfaction-hnn]', text, flags=re.IGNORECASE)
    text = re.sub(r'\bhm+\b', '[dissatisfaction-hnn]', text, flags=re.IGNORECASE)
    
    # Surprise: oà, uoà, ồ
    text = re.sub(r'\b[u]?[oò]à\b', '[surprise-wa]', text, flags=re.IGNORECASE)
    text = re.sub(r'\bồ+\b', '[surprise-oh]', text, flags=re.IGNORECASE)
    text = re.sub(r'\bá+\b', '[surprise-ah]', text, flags=re.IGNORECASE)
    
    return text
