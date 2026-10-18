"""Conservative field descriptions for HLB02_Core_1.52 SharedObject.

Only field presence and type are verified. Interpretations of game mechanics are
intentionally described as hypotheses, not verified limits or unlock semantics.
"""
from __future__ import annotations

from dataclasses import dataclass

CATEGORIES = [
    '全部字段', '进度与日期', '心值与视图', '角色状态', '统计计数', '外观与配色',
    '内部内容标志', '音量与音效', '画面与性能', '交互与操作', '语言与系统', '未分类'
]

@dataclass(frozen=True)
class FieldInfo:
    category: str
    label: str
    description: str
    confidence: str = '字段名推断'  # 仅结构确认 / 字段名推断 / 机制待验证
    bounds: tuple[float, float] | None = None


def f(cat, label, desc, level='字段名推断', bounds=None):
    return FieldInfo(cat, label, desc, level, bounds)

TOP: dict[str, FieldInfo] = {
    'DAYS': f('进度与日期', '当前日数', '游戏日数计数器；数值可见，具体递增时点未验证。'),
    'TopDays': f('进度与日期', '记录日数', '名称暗示历史最高日数，未通过运行时验证。'),
    'DateLast': f('进度与日期', '最后记录日期', 'AMF3 Date（毫秒时间戳），存档中已确认其类型。','仅结构确认'),
    'Total_TimeLast': f('进度与日期', '累计时间相关数值', '时间计数字段；计量单位及重置方式待验证。','机制待验证'),
    'DayHeart': f('心值与视图', '当日心值', '可能与每日心值有关；不能由字段名证明是好感度或给出上限。','机制待验证'),
    'ViewHeart': f('心值与视图', '心形显示模式', '字符串型视图选项；已观察到 none / container 两种值。','仅结构确认'),
    'Horny': f('角色状态', '内部状态 Horny', '数值型角色状态；确切触发条件、取值范围未验证。','机制待验证'),
    'Broke': f('角色状态', '内部状态 Broke', '数值型角色状态；确切含义待运行时验证。','机制待验证'),
    'myPubes': f('外观与配色', '外观标志 myPubes', '外观相关内部标志，保留原名；不同样本值为 0/1。','机制待验证'),
    'LockEye': f('外观与配色', '眼部配饰标志', '嵌套结构；当前包含 glasses。','仅结构确认'),
    'LockCos': f('外观与配色', '服装款式标志', '嵌套结构；可展开全部子字段。','仅结构确认'),
    'LockColor': f('外观与配色', '外观配色标志', '嵌套对象下有数组；逐个索引修改而非覆盖整组。','仅结构确认'),
    'LockFilm': f('内部内容标志', '内容标志 LockFilm', '对象中的子项可能是内容解锁标志，实际含义未知。','机制待验证'),
    'LockFeel': f('内部内容标志', '内部标志 LockFeel', '数值子项可见，不能仅靠 Feel 一词认定为敏感度。','机制待验证'),
    'LockSexM1': f('内部内容标志', '内部标志组 M1', '游戏内部状态/内容标志，按原始字段展示，不提供未验证预设。','机制待验证'),
    'LockSexD1': f('内部内容标志', '内部标志组 D1', '游戏内部状态/内容标志，按原始字段展示。','机制待验证'),
    'LockSexFe': f('内部内容标志', '内部标志组 Fe', '游戏内部状态/内容标志，按原始字段展示。','机制待验证'),
    'VolumeMaster': f('音量与音效', '主音量', '浮点音量参数；建议保持在 0～1。','字段名推断',(0,1)),
    'VolumeBGM': f('音量与音效', '背景音乐音量', '建议保持在 0～1。','字段名推断',(0,1)),
    'VolumeSound': f('音量与音效', '声音音量', '建议保持在 0～1。','字段名推断',(0,1)),
    'VolumeEffect': f('音量与音效', '效果音量', '建议保持在 0～1。','字段名推断',(0,1)),
    'VolumeVoice': f('音量与音效', '语音音量', '建议保持在 0～1。','字段名推断',(0,1)),
    'Mute': f('音量与音效', '静音开关', '布尔类型。','仅结构确认'),
    'ViewQuality': f('画面与性能', '画质预设', '字符串选项，样本观察到 HIGH。','仅结构确认'),
    'ViewMode': f('画面与性能', '窗口模式', '字符串选项，样本观察到 windowed。','仅结构确认'),
    'showFPS': f('画面与性能', '显示 FPS', '布尔类型。','字段名推断'),
    'scaleAutoW': f('画面与性能', '自动缩放 W', '显示缩放开关；具体行为未验证。'),
    'scaleAutoF': f('画面与性能', '自动缩放 F', '显示缩放开关；具体行为未验证。'),
    'Reso_F_W': f('画面与性能', '全屏比例宽', '分辨率/缩放相关浮点量，建议保持 0～1。','字段名推断',(0,1)),
    'Reso_F_H': f('画面与性能', '全屏比例高', '分辨率/缩放相关浮点量，建议保持 0～1。','字段名推断',(0,1)),
    'Reso_D_W': f('画面与性能', '窗口比例宽', '分辨率/缩放相关浮点量，建议保持 0～1。','字段名推断',(0,1)),
    'Reso_D_H': f('画面与性能', '窗口比例高', '分辨率/缩放相关浮点量，建议保持 0～1。','字段名推断',(0,1)),
    'SCZoomAuto': f('画面与性能', '场景自动缩放', '缩放相关浮点量，建议保持 0～1。','字段名推断',(0,1)),
    'MeAlpha': f('画面与性能', '主体透明度', 'Alpha 相关数值，建议保持 0～1。','字段名推断',(0,1)),
    'HandAlpha': f('画面与性能', '界面手势透明度', 'Alpha 相关数值，建议保持 0～1。','字段名推断',(0,1)),
    'ShakeLV': f('画面与性能', '震动强度', '显示反馈强度，建议保持 0～1。','字段名推断',(0,1)),
    'ShakeMode': f('画面与性能', '震动开关', '布尔类型。','字段名推断'),
    'MouseLeftKey': f('交互与操作', '鼠标左键映射', '当前观察到 DRAG。','仅结构确认'),
    'MouseRightKey': f('交互与操作', '鼠标右键映射', '当前观察到 AUTO。','仅结构确认'),
    'autoTypeTouch': f('交互与操作', '触控操作类型', '当前观察到 TAP。','仅结构确认'),
    'MainHand': f('交互与操作', '惯用手', '当前观察到 R。','仅结构确认'),
    'MainSide': f('交互与操作', '侧边偏好', '当前观察到 R。','仅结构确认'),
    'sideBoard': f('交互与操作', '侧栏', '布尔类型，具体作用待验证。'),
    'qhelp': f('交互与操作', '帮助提示', '布尔类型，具体作用待验证。'),
    'qrec': f('交互与操作', '记录提示', '布尔类型，具体作用待验证。'),
    'RecMode': f('交互与操作', '记录模式', '布尔类型，具体作用待验证。'),
    'Lang': f('语言与系统', '语言代码', '样本值为 CHT，其他有效代码应以游戏支持范围为准。','仅结构确认'),
    'Version': f('语言与系统', '游戏存档版本', '观察到 1.52；不建议更改，版本字段不等同于格式转换。','仅结构确认'),
    'Agreement': f('语言与系统', '同意记录', '布尔类型。','仅结构确认'),
}

for k in ('Total_Anside','Total_Cum','Total_Facial','Total_PistonAN','Total_Tear',
          'Total_Mouth','Total_Lost','Total_Orgsam','Total_Inside','Total_Piston'):
    TOP[k] = f('统计计数', k, f'原始计数器 {k}；仅确认数值，不推定增长条件或上限。','机制待验证')


def get_info(path_text: str) -> FieldInfo:
    root = path_text.split('.', 1)[0].split('[', 1)[0]
    info = TOP.get(root, f('未分类', root, '未知字段；显示原始类型和值。','机制待验证'))
    if path_text == root:
        return info
    relative = path_text[len(root):].lstrip('.')
    return FieldInfo(info.category, f'{info.label} · {relative}',
        f'{info.description} 子项：{relative}。未验证的数值上限不会自动套用。',
        info.confidence, info.bounds)
