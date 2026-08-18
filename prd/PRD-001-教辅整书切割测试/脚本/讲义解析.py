# -*- coding: utf-8 -*-
"""
讲义解析层：docx -> 块流（图在流内）+ 标记识别。
🔴 解析层（OMML/上下标/图抽取/表格）**复用** 切割测试-20260817/切割.py，本文件不重造。
本文件只加「教辅讲义方言」的标记识别与结构判定。
"""
import sys, os, re, json, importlib.util
sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CUTTER_PY = r'D:\workplace\ai-bkb-v2\切割测试-20260817\切割.py'

def load_cutter():
    spec = importlib.util.spec_from_file_location('cutter_v1', CUTTER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

C = load_cutter()
import docx
from lxml import etree

# ============================================================
# 一、方言标记正则（方言A·"同步典例考点讲义"系列）
#   来源：老区 录书工作区/小学数学管线/README.md §0/§8/§10/§11（只读考古）
#   + 本卡 2026-08-18 全书实测（3285 段）校准
# ============================================================
# 行首装饰图占位符会挡锚定（老区 §11 老坑 / §16.2 token 版）——分类前先剥
RE_LEAD_TOKEN = re.compile(r'^[\s\u3000]*(?:〖[^〗]*〗|⟦[^⟧]*⟧)+')

RE_UNIT     = re.compile(r'^[\s\u3000]*(第[一二三四五六七八九十百\d]+单元)[\s\u3000]*(.*)$')
RE_PART     = re.compile(r'^[\s\u3000]*【第([一二三四五六七八九十\d]+)部分】[\s\u3000]*(.*)$')
RE_KP       = re.compile(r'^[\s\u3000]*【考点([一二三四五六七八九十百\d]+)】[\s\u3000]*(.*)$')
RE_EXPLAIN  = re.compile(r'^[\s\u3000]*【(方法点拨|名师点拨|易错点拨)】[\s\u3000]*(.*)$')
RE_EXAMPLE  = re.compile(r'^[\s\u3000]*【(典型例题|典例分析|典例精讲|例题)[\s\u3000]*(\d*)】[\s\u3000]*(.*)$')
RE_PRACTICE = re.compile(r'^[\s\u3000]*【(对应练习|变式训练|变式|巩固练习|课后练习)[\s\u3000]*(\d*)】[\s\u3000]*(.*)$')
# 单元头尾巴上的【N大考点】（目录行与正文单元头都可能带）
RE_UNIT_KPN = re.compile(r'【([一二三四五六七八九十百\d]+)大考点】')

MARK_ORDER = ['unit', 'part', 'kp', 'explain', 'example', 'practice']

def strip_lead_token(t):
    return RE_LEAD_TOKEN.sub('', t)

def classify(text):
    """返回 (kind, meta) —— kind ∈ unit/part/kp/explain/example/practice/None"""
    t = strip_lead_token(text or '')
    m = RE_PART.match(t)
    if m:
        return 'part', {'no': m.group(1), 'title': m.group(2).strip()}
    m = RE_KP.match(t)
    if m:
        return 'kp', {'no': m.group(1), 'title': m.group(2).strip()}
    m = RE_EXPLAIN.match(t)
    if m:
        return 'explain', {'label': m.group(1), 'rest': m.group(2)}
    m = RE_EXAMPLE.match(t)
    if m:
        return 'example', {'label': m.group(1), 'no': m.group(2), 'title': m.group(3)}
    m = RE_PRACTICE.match(t)
    if m:
        return 'practice', {'label': m.group(1), 'no': m.group(2), 'title': m.group(3)}
    m = RE_UNIT.match(t)
    if m and '【考点' not in t:
        kpn = RE_UNIT_KPN.search(t)
        title = RE_UNIT_KPN.sub('', m.group(2)).strip()
        # 单元头必须短（正文里"第一单元"三个字也可能出现在题面中）
        if len(t) <= 40:
            return 'unit', {'unit': m.group(1), 'title': title,
                            'kp_count_cn': kpn.group(1) if kpn else ''}
    return None, {}

# ============================================================
# 二、块流构建（复用切割.py 的解析层）
# ============================================================
def build_stream(src, imgdir):
    """docx -> [{'kind':'p'|'tbl','blocks':[...],'head':str,'i':int}] + 基准计数"""
    C.IMGDIR = imgdir
    C.IMG_SEQ[0] = 0
    C.IMG_CACHE.clear()
    os.makedirs(imgdir, exist_ok=True)
    d = docx.Document(src)
    part, body = d.part, d.element.body

    figels = []
    for tag in ('drawing', 'pict', 'object'):
        figels.extend(body.findall('.//' + C.w(tag)))
    figset = set(id(e) for e in figels)
    base = {
        'fig': sum(1 for e in figels if not any(id(a) in figset for a in e.iterancestors())),
        'omath': len(body.findall('.//' + C.m('oMath'))),
        'tbl': len(body.findall('.//' + C.w('tbl'))),
    }

    stream = []
    for ch in body.iterchildren():
        if not isinstance(ch.tag, str):
            continue
        ln = etree.QName(ch).localname
        if ln == 'p':
            spans = C.para_to_spans(ch, part)
            blocks = C.split_spans_into_blocks(spans, part)
            if not blocks:
                continue
            C.stamp_pidx(blocks, len(stream))
            st = ''
            ppr = ch.find(C.w('pPr'))
            if ppr is not None:
                ps = ppr.find(C.w('pStyle'))
                if ps is not None:
                    st = ps.get(C.w('val')) or ''
            stream.append({'kind': 'p', 'blocks': blocks,
                           'head': C.block_head_text(blocks), 'style': st,
                           'i': len(stream)})
        elif ln == 'tbl':
            tb = C.table_to_block(ch, part)
            C.stamp_pidx([tb], len(stream))
            stream.append({'kind': 'tbl', 'blocks': [tb], 'head': '', 'style': '',
                           'i': len(stream)})
    return stream, base

def stream_text(node):
    """节点的可读文本（表格用线性化文本）"""
    out = []
    for b in node['blocks']:
        if b['type'] == 'text':
            out.append(b['text'])
        elif b['type'] == 'figure':
            out.append('')
        elif b['type'] == 'table':
            out.append(b.get('flat_text') or '')
    return '\n'.join(x for x in out if x)

def count_figs(node):
    return sum(1 for b in C.iter_blocks(node['blocks']) if b['type'] == 'figure')
