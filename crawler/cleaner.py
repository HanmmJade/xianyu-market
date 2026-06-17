# -*- coding: utf-8 -*-
"""
数据清洗模块 — 型号精准过滤 + 成色智能推断

设计原则：
1. 搜索用宽泛关键词（保证召回率），清洗用严格规则（保证精确率）
2. 成色以卖家描述中的实际瑕疵为准，不信任卖家自标
3. 脏数据（非球拍商品）100%拦截
4. 型号匹配基于中羽在线装备库别名数据库，不区分大小写
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger


# ============================================================
# 一、型号数据库加载（中羽在线装备库别名）
# ============================================================

_RACKET_DB = None          # {official_name: {brand, aliases, source}}
_ALIAS_LOOKUP = None       # {alias_upper: official_name} 反向查找表
_DB_LOADED = False

def _load_racket_db():
    """加载球拍型号数据库，构建反向别名查找表"""
    global _RACKET_DB, _ALIAS_LOOKUP, _DB_LOADED
    if _DB_LOADED:
        return

    db_path = Path(__file__).parent.parent / "config" / "racket_database.json"
    if not db_path.exists():
        logger.warning(f"[型号库] 数据库文件不存在: {db_path}")
        _RACKET_DB = {}
        _ALIAS_LOOKUP = {}
        _DB_LOADED = True
        return

    with open(db_path, 'r', encoding='utf-8') as f:
        _RACKET_DB = json.load(f)

    # 构建反向查找表：alias(大写) → official_name
    _ALIAS_LOOKUP = {}
    for official_name, info in _RACKET_DB.items():
        # 官方名本身也能匹配
        _ALIAS_LOOKUP[official_name.upper()] = official_name
        # 所有别名
        for alias in info.get("aliases", []):
            _ALIAS_LOOKUP[alias.upper()] = official_name

    logger.info(f"[型号库] 已加载 {len(_RACKET_DB)} 个型号，{len(_ALIAS_LOOKUP)} 个别名")
    _DB_LOADED = True


def get_racket_db() -> Dict:
    """获取型号数据库（懒加载）"""
    _load_racket_db()
    return _RACKET_DB


def get_alias_lookup() -> Dict:
    """获取别名反向查找表（懒加载）"""
    _load_racket_db()
    return _ALIAS_LOOKUP


# ============================================================
# 二、型号精准过滤规则（补充数据库的歧义消解）
# ============================================================

# 当多个型号共享同一个别名时，需要额外规则消歧
# 例如："疾光800"可能匹配 NF800PRO 也可能匹配 NF800 TOUR
# 这些规则只在数据库匹配产生歧义时使用

MODEL_DISAMBIGUATION = {
    # NF800 系列消歧
    "NANOFLARE 800 PRO": {
        # 排除词：包含这些词的不是 800PRO
        "exclude": ["800 TOUR", "800TOUR", "NF-800 TOUR", "800 GAME", "800GAME", "800 PLAY", "800PLAY"],
        # 裸写"疾光800"/"NF800"（无PRO/TOUR/GAME/PLAY后缀）时，排除
        # 因为"疾光800"可能是800（老款）也可能是800PRO，无法确定
        "bare_exclude": ["疾光800", "NF800", "NANOFLARE800", "NANOFLARE 800", "NF-800"],
        "bare_rescue": ["800PRO", "800LT", "800PRO", "800LT"],
    },
    # 88D PRO vs 88S PRO 消歧
    "ASTROX 88D PRO": {
        "exclude": ["88S PRO", "88SPRO", "88SP"],
        "bare_rescue": ["88DPRO", "88DP", "88D PRO"],
    },
    "ASTROX 88S PRO": {
        "exclude": ["88D PRO", "88DPRO", "88DP"],
        "bare_rescue": ["88SPRO", "88SP", "88S PRO"],
    },
    # 100ZZ vs 1000Z 消歧
    "ASTROX 100ZZ": {
        "exclude": ["1000Z", "1000ZZ", "100 TOUR", "100TOUR", "100 GAME", "100GAME"],
        "bare_rescue": ["100ZZ", "100VAZZ"],
    },
    # 弓箭11PRO vs 弓箭11 消歧
    "ARCSABER 11 PRO": {
        "exclude": ["11 TOUR", "11TOUR", "11 PLAY", "11PLAY"],
        "bare_rescue": ["ARC11PRO", "弓箭11PRO"],
    },
    # 风刃500 PRO vs 风刃500 消歧
    "3D CALIBAR 500 PRO": {
        "exclude": [],
        "bare_rescue": ["风刃500PRO", "CALIBAR500PRO"],
    },
    # 雷霆80 II vs 雷霆80 消歧
    "雷霆80 II": {
        "exclude": [],
        "bare_rescue": ["雷霆80二代", "AXFORCE80II", "雷霆80II"],
    },
}


def _normalize(text: str) -> str:
    """统一大小写（全大写），去除多余空格。所有型号匹配必须经过此函数。"""
    return re.sub(r'\s+', '', text.upper())


def classify_model(title: str, model_name: str, record_model: str = "") -> Tuple[bool, str]:
    """
    精确判断一条记录是否属于指定型号。

    匹配流程：
    1. 查中羽在线别名数据库（100型号，278别名）
    2. 歧义消解（88D vs 88S，100ZZ vs 1000Z 等）
    3. 数据库无匹配时放行（可能是新型号）

    参数:
        title: 商品标题
        model_name: 目标型号（如 "疾光NF800PRO" 或 "NANOFLARE 800 PRO"）
        record_model: 记录自带的型号字段（爬虫匹配的原始型号名）

    返回: (是否匹配, 原因)
    """
    _load_racket_db()

    t_upper = _normalize(title)
    t_lower = title.lower()

    # Step 1: 尝试用 model_name 查数据库
    model_info = _RACKET_DB.get(model_name)

    # Step 1b: 如果 model_name 不在数据库，尝试用 record_model
    if not model_info and record_model:
        model_info = _RACKET_DB.get(record_model)
        if model_info:
            model_name = record_model  # 用数据库里的正式名称

    # Step 1c: 如果都不在数据库，尝试在别名表里查找
    if not model_info:
        # 用 model_name 在别名表里反查
        normalized_name = _normalize(model_name)
        db_name = _ALIAS_LOOKUP.get(normalized_name)
        if db_name:
            model_info = _RACKET_DB.get(db_name)
            if model_info:
                model_name = db_name

    if not model_info and record_model:
        normalized_record = _normalize(record_model)
        db_name = _ALIAS_LOOKUP.get(normalized_record)
        if db_name:
            model_info = _RACKET_DB.get(db_name)
            if model_info:
                model_name = db_name

    if model_info:
        aliases = model_info.get("aliases", [])
        # 构建该型号的匹配集合（全大写，去空格）
        match_set = set()
        match_set.add(_normalize(model_name))
        for alias in aliases:
            match_set.add(_normalize(alias))

        # 检查标题是否包含任何一个别名
        matched_alias = None
        for alias_norm in match_set:
            if alias_norm in t_upper:
                matched_alias = alias_norm
                break

        if not matched_alias:
            # 没匹配到任何别名 → 不是这个型号
            return False, f"no_alias_match:{model_name}"

        # Step 2: 歧义消解
        disambig = MODEL_DISAMBIGUATION.get(model_name)
        if disambig:
            # 检查排除词
            for exc in disambig.get("exclude", []):
                if _normalize(exc) in t_upper:
                    return False, f"disambig_excluded:{exc}"

            # 检查裸写排除（如"疾光800"无PRO后缀，可能是老款）
            for bare in disambig.get("bare_exclude", []):
                bare_norm = _normalize(bare)
                if bare_norm in t_upper:
                    # 有裸写词，但检查是否有 rescue 词（如"800PRO"）
                    has_rescue = False
                    for rescue in disambig.get("bare_rescue", []):
                        if _normalize(rescue) in t_upper:
                            has_rescue = True
                            break
                    if not has_rescue:
                        return False, f"bare_model_no_variant:{bare}"

        return True, f"db_matched:{matched_alias}"

    # Step 3: 数据库中没有这个型号（可能是新型号或未收录）
    # 放行，不拦截
    return True, "not_in_db_passthrough"


# ============================================================
# 二、成色智能推断
# ============================================================

# 扣分规则：(关键词, 分数变化, 描述)
# 正数=加分，负数=扣分
# 注意：所有关键词匹配均使用 .lower() 比较，不区分大小写
CONDITION_RULES = [
    # ---- 正面加分 ----
    {"keywords": ["全新", "未使用", "未拆封", "未开封"], "score": 100, "absolute": True,
     "desc": "全新/未使用", "priority": 1,
     # "全新"后面跟"护线管""手胶""线"等配件词时，不是说整支拍全新
     "exclude_after": ["护线管", "手胶", "线管", "穿线", "磅线", "底胶"]},
    {"keywords": ["质保卡", "电子质保", "有质保"], "score": 3, "absolute": False,
     "desc": "有质保", "priority": 5},
    {"keywords": ["首线无暇", "首线无瑕", "首线未剪"], "score": 2, "absolute": False,
     "desc": "首线无暇", "priority": 5},
    {"keywords": ["无修无塌无内伤", "无修复无塌陷无内伤"], "score": 3, "absolute": False,
     "desc": "无修无塌无内伤", "priority": 4},
    {"keywords": ["过x光", "已过x光", "x光验拍"], "score": 2, "absolute": False,
     "desc": "已过X光验证", "priority": 5},

    # ---- 轻微瑕疵（-2~5分）----
    {"keywords": ["轻微磨损", "轻微划痕", "轻微痕迹", "轻微使用"], "score": -3, "absolute": False,
     "desc": "轻微磨损/划痕", "priority": 10},
    {"keywords": ["米粒瑕", "芝麻瑕", "针尖瑕"], "score": -3, "absolute": False,
     "desc": "米粒/芝麻瑕", "priority": 10},
    {"keywords": ["贴纸瑕"], "score": -2, "absolute": False,
     "desc": "贴纸瑕", "priority": 10},
    {"keywords": ["去底胶", "去底"], "score": -1, "absolute": False,
     "desc": "去底胶", "priority": 12},

    # ---- 中等瑕疵（-5~10分）----
    {"keywords": ["大掉漆", "多处掉漆", "三个掉漆", "3个掉漆"], "score": -10, "absolute": False,
     "desc": "大面积掉漆", "priority": 20},
    {"keywords": ["两处掉漆", "2处掉漆"], "score": -6, "absolute": False,
     "desc": "两处掉漆", "priority": 20},
    {"keywords": ["掉漆"], "score": -5, "absolute": False,
     "desc": "有掉漆", "priority": 21},  # 优先级低于更具体的规则
    {"keywords": ["磕碰"], "score": -5, "absolute": False,
     "desc": "有磕碰", "priority": 20},

    # ---- 翻新处理（-5~10分）----
    {"keywords": ["翻新"], "score": -8, "absolute": False,
     "desc": "翻新处理", "priority": 25},
    {"keywords": ["补漆"], "score": -5, "absolute": False,
     "desc": "补漆", "priority": 25},
    {"keywords": ["更换护线管", "全新护线管"], "score": -2, "absolute": False,
     "desc": "换过护线管", "priority": 26},

    # ---- 严重问题（-15~25分）----
    # 注意：必须排除"无塌""无修"等否定表述
    {"keywords": ["有塌陷", "轻微塌陷", "部分塌陷"], "score": -15, "absolute": False,
     "desc": "有塌陷", "priority": 30},
    {"keywords": ["有修复", "已修复", "完成修复", "修复正常"], "score": -20, "absolute": False,
     "desc": "有修复", "priority": 30},
    {"keywords": ["裂缝", "裂纹"], "score": -15, "absolute": False,
     "desc": "有裂缝", "priority": 30},
    {"keywords": ["断裂", "断拍", "有断"], "score": -25, "absolute": False,
     "desc": "有断裂", "priority": 30},
    {"keywords": ["暗伤", "内伤"], "score": -10, "absolute": False,
     "desc": "有暗伤/内伤", "priority": 30},
]


def _check_negative_context(title: str, keyword: str) -> bool:
    """
    检查关键词是否在否定语境中（如"无塌陷""无修复"）。
    返回 True 表示是否定语境，应跳过此规则。
    """
    t = title.lower()
    kw = keyword.lower()

    # 否定前缀
    neg_prefixes = ["无", "没有", "没", "不", "未", "非", "零"]
    for prefix in neg_prefixes:
        # 直接检查"无塌陷""无修复"等
        neg_form = prefix + kw
        if neg_form in t:
            return True
        # 也检查"无塌 无修"这种中间有空格的情况
        neg_form_spaced = prefix + " " + kw
        if neg_form_spaced in t:
            return True

    # 特殊否定短语（"无断补"、"无断补"等）
    special_negations = ["无断补", "无断补", "无断痕", "无裂纹", "无裂缝"]
    for sn in special_negations:
        if sn in t:
            return True

    return False


def infer_condition(title: str) -> Dict:
    """
    从卖家描述推断真实成色。

    返回: {
        "label": "全新" / "95新" / "9新" / "85新" / "8新" / "8新以下",
        "score": 0-100,
        "evidence": [扣分/加分依据列表],
        "has_severe_issue": bool,  # 是否有严重问题（塌陷/修复/裂缝）
    }
    """
    evidence = []
    score = 90  # 基准分（假设良好状态）
    is_brand_new = False
    has_severe = False
    has_refurbish = False

    # 按优先级排序，逐条检查
    sorted_rules = sorted(CONDITION_RULES, key=lambda r: r.get("priority", 50))

    matched_rules = set()  # 防止同一条规则重复匹配（用规则索引）

    for rule_idx, rule in enumerate(sorted_rules):
        for kw in rule["keywords"]:
            # 检查是否在标题中出现
            if kw.lower() not in title.lower():
                continue

            # 检查排除后缀（如"全新护线管"不是"全新"）
            exclude_after = rule.get("exclude_after", [])
            if exclude_after:
                kw_pos = title.lower().find(kw.lower())
                if kw_pos >= 0:
                    after_kw = title[kw_pos + len(kw):]
                    skip = False
                    for exc in exclude_after:
                        if after_kw.startswith(exc) or after_kw.startswith(" " + exc):
                            skip = True
                            break
                    if skip:
                        continue

            # 检查否定语境（"无塌陷"不扣分）
            if rule["score"] < 0 and _check_negative_context(title, kw):
                continue

            # 匹配成功
            matched_rules.add(rule_idx)

            if rule.get("absolute"):
                # 绝对值设置（如"全新"直接设为100分）
                # 注意：后续的翻新/瑕疵扣分仍然生效
                if rule["score"] > score and not is_brand_new:
                    score = rule["score"]
                    is_brand_new = True
                    evidence.insert(0, rule["desc"])
            else:
                score += rule["score"]
                evidence.append(f"{rule['desc']}({'+' if rule['score'] > 0 else ''}{rule['score']}分)")

                # 标记严重问题
                if rule["score"] <= -15:
                    has_severe = True
                if rule["score"] <= -8 and "翻新" in rule["desc"]:
                    has_refurbish = True

            break  # 这条规则已匹配，不再检查同规则的其他关键词

    # 交叉验证：卖家自标成色 vs 实际描述
    claimed_conditions = {
        "全新": ["全新"], "99新": ["99新", "99"], "95新": ["95新", "95"],
        "9新": ["9新", "九成新"], "85新": ["85新"], "8新": ["8新", "八成新"],
    }
    claimed = ""
    for cond_label, keywords in claimed_conditions.items():
        for kw in keywords:
            if kw in title:
                claimed = cond_label
                break
        if claimed:
            break

    # 分数边界校准
    score = max(0, min(100, score))

    # 映射成色标签
    if score >= 98:
        label = "全新"
    elif score >= 90:
        label = "95新"
    elif score >= 82:
        label = "9新"
    elif score >= 72:
        label = "85新"
    elif score >= 60:
        label = "8新"
    else:
        label = "8新以下"

    # 虚标检测
    if claimed and claimed != label:
        severity = ""
        if claimed in ("全新", "99新") and score < 85:
            severity = "⚠️严重虚标"
        elif claimed in ("95新",) and score < 75:
            severity = "⚠️虚标"
        if severity:
            evidence.append(f"{severity}：卖家声称{claimed}，实际推断{label}")

    return {
        "label": label,
        "score": score,
        "evidence": evidence,
        "claimed": claimed,
        "has_severe_issue": has_severe,
        "has_refurbish": has_refurbish,
    }


# ============================================================
# 三、脏数据检测
# ============================================================

# 非球拍商品的特征关键词（必须是独立完整匹配，不能误伤球拍描述）
GARBAGE_PATTERNS = [
    # 电子产品（必须完整出现独立词）
    r"(主机|显卡|CPU|主板|内存条|固态硬盘|机箱|RTX\d|GTX\d|i5-\d|i7-\d|i9-\d|Ryzen\d|游戏机|游戏主机)",
    r"(笔记本电脑|显示器|机械键盘|鼠标|耳机|音箱|手机壳|平板电脑|iPad|iPhone|华为手机|小米手机)",
    # 服装鞋帽（排除"球鞋"等运动装备的误伤）
    r"(运动鞋|休闲鞋|衣服|裤子|帽子|手表|项链|戒指|手链|T恤|夹克|外套)",
    # 生活用品
    r"(化妆品|护肤品|零食|食品|家具|椅子|桌子|床架|床垫)",
    # 虚拟物品
    r"(游戏账号|充值卡|会员卡|VIP卡|优惠券|代金券|门票)",
    # 其他运动器材（排除羽毛球拍本身）
    r"(网球拍|乒乓球拍|壁球拍|高尔夫球杆|滑雪板|自行车)",
    # 汽车配件
    r"(轮胎|轮毂|刹车片|机油|滤芯|排气管)",
]

# 但如果是球拍相关的配件和球拍一起卖，不算脏数据
# 注意：只放球拍领域专有词，不放"正品""成色"等通用词
GARBAGE_WHITELIST = [
    "送线", "带线", "穿线", "送手胶", "带手胶",
    "送拍套", "带拍套", "含线", "首线",
    "羽毛球拍", "羽拍", "球拍", "4U", "3U", "5U",
    "磅", "磅线", "BG", "bg", "手胶", "底胶",
    "掉漆", "磕碰", "护线管", "去底",
    "羽毛球", "穿线", "拉线",
]


def is_garbage(title: str) -> Tuple[bool, str]:
    """
    检测是否为脏数据（非球拍商品）。

    返回: (是否脏数据, 原因)

    逻辑：先检查白名单（球拍相关词），命中则直接放行。
    再检查垃圾模式，命中才判定为脏数据。
    """
    # 白名单优先：如果包含球拍相关描述，直接放行
    for wl in GARBAGE_WHITELIST:
        if wl.lower() in title.lower():
            return False, "whitelist_hit"

    # 再检查垃圾模式
    for pattern in GARBAGE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True, f"garbage_pattern:{pattern}"

    return False, "clean"


# ============================================================
# 四、价格异常检测
# ============================================================

def check_price_anomaly(price: float, model_name: str) -> Tuple[bool, str]:
    """
    检测价格是否异常（太低或太高）。

    返回: (是否异常, 原因)
    """
    # 型号价格合理区间（最低，最高）
    PRICE_RANGES = {
        "疾光NF800PRO": (300, 2000),
        "天斧88D PRO": (300, 2000),
        "天斧100ZZ": (300, 2500),
        "天斧77PRO": (300, 2000),
        "弓箭11PRO": (200, 1800),
        "风刃900": (200, 1200),
        "风刃900i": (200, 1200),
        "雷霆80": (200, 1500),
        "战戟8000": (300, 1500),
        "神速100X": (200, 1200),
        "龙牙之刃": (300, 1500),
        "极速10": (150, 800),
    }

    # 尝试精确匹配
    for model_key, (low, high) in PRICE_RANGES.items():
        if model_key in model_name or model_name in model_key:
            if price < low:
                return True, f"价格过低(¥{price} < ¥{low})"
            if price > high:
                return True, f"价格过高(¥{price} > ¥{high})"
            return False, "normal"

    # 通用范围
    if price < 50:
        return True, f"价格过低(¥{price})"
    if price > 5000:
        return True, f"价格过高(¥{price})"

    return False, "normal"


# ============================================================
# 五、统一清洗管线
# ============================================================

def clean_record(record: Dict, target_model: str = "") -> Dict:
    """
    对单条记录执行完整清洗管线。

    流程：
    1. 脏数据检测
    2. 型号精准过滤
    3. 成色智能推断
    4. 价格异常检测

    返回增强后的记录（带 _clean_pass, _clean_reject 等内部字段）。
    """
    title = record.get("title", "")
    price = record.get("price", 0)
    record_model = record.get("model", "")

    result = dict(record)

    # Step 1: 脏数据检测
    is_bad, reason = is_garbage(title)
    if is_bad:
        result["_clean_pass"] = False
        result["_clean_reject"] = f"garbage:{reason}"
        return result

    # Step 2: 型号精准过滤
    if target_model:
        is_match, match_reason = classify_model(title, target_model, record_model)
        if not is_match:
            result["_clean_pass"] = False
            result["_clean_reject"] = f"model_mismatch:{match_reason}"
            return result
        result["_real_model"] = target_model

    # Step 3: 成色智能推断
    cond = infer_condition(title)
    result["_inferred_condition"] = cond

    # Step 4: 价格异常检测
    model_for_price = target_model or record_model
    is_anomaly, anomaly_reason = check_price_anomaly(price, model_for_price)
    result["_price_anomaly"] = {"is_anomaly": is_anomaly, "reason": anomaly_reason}

    result["_clean_pass"] = True
    return result


def clean_batch(records: List[Dict], target_model: str = "",
                remove_garbage: bool = True, remove_wrong_model: bool = True,
                remove_price_anomaly: bool = False) -> Tuple[List[Dict], Dict]:
    """
    批量清洗记录。

    返回: (清洗后记录列表, 清洗报告)
    """
    report = {
        "total": len(records),
        "garbage_removed": 0,
        "model_mismatch_removed": 0,
        "price_anomaly_flagged": 0,
        "passed": 0,
    }

    cleaned = []
    for r in records:
        result = clean_record(r, target_model=target_model)

        if not result.get("_clean_pass", False):
            reject = result.get("_clean_reject", "")
            if "garbage" in reject:
                report["garbage_removed"] += 1
                if remove_garbage:
                    continue
            elif "model_mismatch" in reject:
                report["model_mismatch_removed"] += 1
                if remove_wrong_model:
                    continue

        if result.get("_price_anomaly", {}).get("is_anomaly"):
            report["price_anomaly_flagged"] += 1
            if remove_price_anomaly:
                continue

        report["passed"] += 1
        cleaned.append(result)

    return cleaned, report
