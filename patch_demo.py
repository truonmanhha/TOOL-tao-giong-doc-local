import re

file_path = r"D:\ALL TOOL\TOOL LÀM YOUTUBE\OmniVoice-master\omnivoice\cli\demo.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update _CATEGORIES
new_categories = """_CATEGORIES = {
    "Giới tính": ["Nam", "Nữ"],
    "Độ tuổi": [
        "Trẻ em",
        "Thiếu niên",
        "Thanh niên",
        "Trung niên",
        "Người già",
    ],
    "Độ cao giọng (Pitch)": [
        "Rất thấp",
        "Thấp",
        "Vừa phải",
        "Cao",
        "Rất cao",
    ],
    "Phong cách": ["Thì thầm"],
    "Khẩu âm Tiếng Anh": [
        "Giọng Mỹ",
        "Giọng Úc",
        "Giọng Anh",
        "Giọng Trung",
        "Giọng Canada",
        "Giọng Ấn Độ",
        "Giọng Hàn Quốc",
        "Giọng Bồ Đào Nha",
        "Giọng Nga",
        "Giọng Nhật Bản",
    ],
    "Phương ngôn Tiếng Trung": [
        "Tiếng Hà Nam",
        "Tiếng Thiểm Tây",
        "Tiếng Tứ Xuyên",
        "Tiếng Quý Châu",
        "Tiếng Vân Nam",
        "Tiếng Quế Lâm",
        "Tiếng Tế Nam",
        "Tiếng Thạch Gia Trang",
        "Tiếng Cam Túc",
        "Tiếng Ninh Hạ",
        "Tiếng Thanh Đảo",
        "Tiếng Đông Bắc",
    ],
}

_VI_TO_INSTRUCT = {
    "Nam": "Male", "Nữ": "Female",
    "Trẻ em": "Child", "Thiếu niên": "Teenager", "Thanh niên": "Young Adult", "Trung niên": "Middle-aged", "Người già": "Elderly",
    "Rất thấp": "Very Low Pitch", "Thấp": "Low Pitch", "Vừa phải": "Moderate Pitch", "Cao": "High Pitch", "Rất cao": "Very High Pitch",
    "Thì thầm": "Whisper",
    "Giọng Mỹ": "American Accent", "Giọng Úc": "Australian Accent", "Giọng Anh": "British Accent", "Giọng Trung": "Chinese Accent",
    "Giọng Canada": "Canadian Accent", "Giọng Ấn Độ": "Indian Accent", "Giọng Hàn Quốc": "Korean Accent", "Giọng Bồ Đào Nha": "Portuguese Accent",
    "Giọng Nga": "Russian Accent", "Giọng Nhật Bản": "Japanese Accent",
    "Tiếng Hà Nam": "河南话", "Tiếng Thiểm Tây": "陕西话", "Tiếng Tứ Xuyên": "四川话", "Tiếng Quý Châu": "贵州话",
    "Tiếng Vân Nam": "云南话", "Tiếng Quế Lâm": "桂林话", "Tiếng Tế Nam": "济南话", "Tiếng Thạch Gia Trang": "石家庄话",
    "Tiếng Cam Túc": "甘肃话", "Tiếng Ninh Hạ": "宁夏话", "Tiếng Thanh Đảo": "青岛话", "Tiếng Đông Bắc": "东北话"
}"""

content = re.sub(r'_CATEGORIES = \{.*?\n\}', new_categories, content, flags=re.DOTALL)

# 2. Update _ATTR_INFO
new_attr_info = """_ATTR_INFO = {
    "Khẩu âm Tiếng Anh": "Chỉ hiệu quả với tiếng Anh.",
    "Phương ngôn Tiếng Trung": "Chỉ hiệu quả với tiếng Trung.",
}"""
content = re.sub(r'_ATTR_INFO = \{.*?\n\}', new_attr_info, content, flags=re.DOTALL)

# 3. Update _ALL_LANGUAGES
content = content.replace('_ALL_LANGUAGES = ["Auto"] + sorted(lang_display_name(n) for n in LANG_NAMES)', '_ALL_LANGUAGES = ["Tự động"] + sorted(lang_display_name(n) for n in LANG_NAMES)')

# 4. Update lang logic in _gen_core
content = content.replace('lang = language if (language and language != "Auto") else None', 'lang = language if (language and language not in ("Auto", "Tự động")) else None')

# 5. Update _lang_dropdown
content = content.replace('def _lang_dropdown(label="Ngôn ngữ (tùy chọn)", value="Auto"):', 'def _lang_dropdown(label="Ngôn ngữ (tùy chọn)", value="Tự động"):')
content = content.replace('info="Để Auto để tự động phát hiện ngôn ngữ."', 'info="Để \'Tự động\' để tự động phát hiện ngôn ngữ."')

# 6. Update Voice Design Tab _AUTO
content = content.replace('_AUTO = "Auto"', '_AUTO = "Tự động"')

# 7. Update _build_instruct
old_build_instruct = '''                def _build_instruct(groups):
                    """Extract instruct text from UI dropdowns.

                    Language unification and validation is handled by
                    _resolve_instruct inside _preprocess_all.
                    """
                    selected = [g for g in groups if g and g != "Auto"]
                    if not selected:
                        return None
                    parts = []
                    for v in selected:
                        if " / " in v:
                            en, zh = v.split(" / ", 1)
                            # Dialects have no English equivalent
                            if "Dialect" in v.split(" / ")[0]:
                                parts.append(zh.strip())
                            else:
                                parts.append(en.strip())
                        else:
                            parts.append(v)
                    return ", ".join(parts)'''

new_build_instruct = '''                def _build_instruct(groups):
                    selected = [g for g in groups if g and g not in ("Auto", "Tự động")]
                    if not selected:
                        return None
                    parts = []
                    for v in selected:
                        parts.append(_VI_TO_INSTRUCT.get(v, v))
                    return ", ".join(parts)'''

content = content.replace(old_build_instruct, new_build_instruct)

# Save
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated successfully")
