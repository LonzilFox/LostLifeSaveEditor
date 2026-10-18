"""Windows GUI for standard Flash AMF3 SharedObject (.sol) saves."""
from __future__ import annotations
import argparse
from collections import Counter
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tkinter as tk
from tkinter import filedialog, ttk
from dialogs import messagebox

from editor_core import (ChangedOnDiskError, EditorSession, collect_leaves,
  describe_diff, export_rows_csv, find_saves, get_info, load_sol)
from field_catalog import CATEGORIES, TOP
from sol_codec import (SolError, format_value, get_at_path, is_leaf, iter_nodes,
  parse_user_value, path_to_text, to_jsonable, validate_roundtrip, value_kind)
import theme as T
import rounded_ui as R
from table_layout import MAIN_COLUMNS, MIN_WIDTH, fitted_columns

APP='SOL Save Editor'
VERSION='0.0.1'


class SaveEditor(tk.Tk):
    def __init__(self, file_path=None):
        super().__init__()
        self.title(f'{APP}  ·  v{VERSION}')
        self.geometry('1580x940')
        self.minsize(1240,760)
        self.configure(bg=T.BG)
        self.option_add('*tearOff',False)
        T.apply(self)
        self.session=EditorSession()
        self.path_by_iid={}
        self.visible=[]
        self.chosen=None
        self.category='全部字段'
        self.nav_widgets={}
        self.search_var=tk.StringVar()
        self.show_modified=tk.BooleanVar(value=False)
        self.show_struct=tk.BooleanVar(value=False)
        self.edit_value=tk.StringVar()
        self.status=tk.StringVar(value='打开 .sol 文件开始。编辑前请备份并关闭游戏。')
        self.backups=tk.BooleanVar(value=True)
        self.source_info=tk.StringVar(value='没有打开文件')
        self.count_info=tk.StringVar(value='—')
        self.editor_status=tk.StringVar(value='选中表格中的字段查看详细信息')
        self.info_title=tk.StringVar(value='选择一个字段')
        self.info_path=tk.StringVar(value='')
        self.info_meta=tk.StringVar(value='')
        self.info_desc=tk.StringVar(value='从左侧选择分类，或搜索变量名。')
        self.info_old=tk.StringVar(value='—')
        self.info_current=tk.StringVar(value='—')
        self._build()
        self.after_idle(lambda: R.prefer_rounded_window(self))
        self.protocol('WM_DELETE_WINDOW',self._close)
        self.bind_all('<Control-z>',lambda e:self.undo())
        self.bind_all('<Control-y>',lambda e:self.redo())
        self.bind_all('<Control-s>',lambda e:self.save())
        self.bind_all('<Control-o>',lambda e:self.open_file())
        self.bind_all('<Control-f>',lambda e:self.search_input.focus_set())
        self.bind_all('<Control-Shift-S>',lambda e:self.save_as())
        if file_path:
            self.after(70,lambda:self.open_path(file_path))

    def _build(self):
        header=tk.Frame(self,bg=T.BG,height=103)
        header.pack(fill='x',padx=24,pady=(17,9))
        header.pack_propagate(False)
        top=tk.Frame(header,bg=T.BG)
        top.pack(fill='x')
        badge=R.RoundedBadge(top,text='S',size=46)
        badge.pack(side='left',padx=(0,12))
        titles=tk.Frame(top,bg=T.BG)
        titles.pack(side='left',fill='y')
        T.label(titles,'SOL SAVE EDITOR',bg=T.BG,color=T.FG,font_size=20,bold=True).pack(anchor='w')
        T.label(titles,'FLASH SHAREDOBJECT  /  AMF3  ·  v0.0.1',bg=T.BG,color=T.PINK,font_size=9).pack(anchor='w')
        R.RoundedButton(top,text='保存修改  Ctrl+S',style='Accent.TButton',command=self.save).pack(side='right',padx=(8,0))
        R.RoundedButton(top,text='另存为',command=self.save_as).pack(side='right',padx=(8,0))
        R.RoundedButton(top,text='打开 SOL',command=self.open_file).pack(side='right',padx=(8,0))
        R.RoundedButton(top,text='自动查找',command=self.auto_find).pack(side='right')
        T.label(header,textvariable=self.source_info,bg=T.BG,color=T.MUTED,font_size=9,anchor='w').pack(fill='x',pady=(7,0))

        main=tk.Frame(self,bg=T.BG)
        main.pack(fill='both',expand=True,padx=20,pady=(0,12))
        self.side_card=R.RoundedPanel(main,width=246,bg=T.PANEL)
        self.side_card.pack(side='left',fill='y',padx=(0,12))
        self.side=self.side_card.body
        side_header=tk.Frame(self.side,bg=T.PANEL)
        side_header.pack(fill='x',padx=15,pady=(18,10))
        T.label(side_header,'字段导航',color=T.FG,bold=True,font_size=12).pack(anchor='w')
        T.label(side_header,'按存档实际字段自动分组',color=T.FAINT,font_size=9).pack(anchor='w',pady=(4,0))
        side_footer=tk.Frame(self.side,bg=T.PANEL)
        side_footer.pack(fill='x',padx=10,pady=(8,4),side='bottom')
        ttk.Separator(side_footer).pack(fill='x',pady=(0,8))
        T.label(side_footer,'安全写回',color=T.PINK,bold=True).pack(anchor='w')
        T.label(side_footer,'备份 · 原子替换 · 落盘回读',color=T.MUTED,font_size=9,wraplength=208,justify='left').pack(anchor='w',pady=(2,0))
        nav_shell=tk.Frame(self.side,bg=T.PANEL)
        nav_shell.pack(fill='both',expand=True,padx=(3,0))
        nav_canvas=tk.Canvas(nav_shell,bg=T.PANEL,bd=0,highlightthickness=0)
        nav_canvas.pack(side='left',fill='both',expand=True)
        nav_scroll=R.RoundedScrollbar(nav_shell,orient='vertical',command=nav_canvas.yview)
        nav_scroll.pack(side='right',fill='y')
        nav_canvas.configure(yscrollcommand=nav_scroll.set)
        nav_container=tk.Frame(nav_canvas,bg=T.PANEL)
        nav_window=nav_canvas.create_window((0,0),window=nav_container,anchor='nw')
        nav_canvas.bind('<Configure>',lambda e:nav_canvas.itemconfigure(nav_window,width=e.width))
        nav_container.bind('<Configure>',lambda e:nav_canvas.configure(scrollregion=nav_canvas.bbox('all')))
        for cat in CATEGORIES:
            btn=R.RoundedNav(nav_container,cat,lambda c=cat:self.set_category(c))
            btn.pack(fill='x',padx=(4,0),pady=1)
            self.nav_widgets[cat]=btn
        self.nav_widgets[self.category].set_selected(True)
        def nav_wheel(event):
            delta = -1 if getattr(event,'num',None)==4 else (1 if getattr(event,'num',None)==5 else -int(event.delta/120))
            nav_canvas.yview_scroll(delta*2,'units')
            return 'break'
        nav_canvas.bind('<MouseWheel>',nav_wheel)
        nav_canvas.bind('<Button-4>',nav_wheel)
        nav_canvas.bind('<Button-5>',nav_wheel)
        for btn in self.nav_widgets.values():
            btn.bind('<MouseWheel>',nav_wheel,add='+')
            btn.bind('<Button-4>',nav_wheel,add='+')
            btn.bind('<Button-5>',nav_wheel,add='+')

        right=tk.Frame(main,bg=T.BG)
        right.pack(side='left',fill='both',expand=True)
        stats=tk.Frame(right,bg=T.BG)
        stats.pack(fill='x',pady=(0,11))
        for label, key in [('顶层字段','top'),('可编辑值','leaf'),('未保存更改','changed'),('结构节点','total')]:
            card=R.RoundedPanel(stats,width=156,height=91,bg=T.PANEL,radius=17,inset=9)
            card.pack(side='left',fill='x',expand=True,padx=(0,8))
            frame=card.body
            T.label(frame,label,color=T.MUTED,font_size=9).pack(anchor='w',padx=4,pady=(2,0))
            count=T.label(frame,'—',color=T.PINK if key=='changed' else T.FG,font_size=19,bold=True)
            count.pack(anchor='w',padx=4,pady=(0,2))
            setattr(self,'stat_'+key,count)

        content=tk.Frame(right,bg=T.BG)
        content.pack(fill='both',expand=True)
        center_card=R.RoundedPanel(content,bg=T.PANEL, radius=18,inset=9)
        center_card.pack(side='left',fill='both',expand=True,padx=(0,10))
        center=center_card.body
        inspector_card=R.RoundedPanel(content,bg=T.PANEL,width=335,radius=18,inset=10)
        inspector_card.pack(side='right',fill='y')
        inspector_shell=inspector_card.body
        inspector_canvas=tk.Canvas(inspector_shell,bg=T.PANEL,highlightthickness=0,bd=0)
        inspector_canvas.pack(side='left',fill='both',expand=True)
        inspector_scroll=R.RoundedScrollbar(inspector_shell,orient='vertical',command=inspector_canvas.yview)
        inspector_scroll.pack(side='right',fill='y')
        inspector_canvas.configure(yscrollcommand=inspector_scroll.set)
        inspector=tk.Frame(inspector_canvas,bg=T.PANEL)
        inspector_window=inspector_canvas.create_window((0,0),window=inspector,anchor='nw')
        inspector.bind('<Configure>',lambda event: inspector_canvas.configure(scrollregion=inspector_canvas.bbox('all')))
        inspector_canvas.bind('<Configure>',lambda event:inspector_canvas.itemconfigure(inspector_window,width=event.width))
        def inspector_wheel(event):
            delta = -1 if getattr(event,'num',None)==4 else (1 if getattr(event,'num',None)==5 else -int(event.delta/120))
            inspector_canvas.yview_scroll(delta*2,'units')
            return 'break'
        for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):
            inspector.bind(sequence,inspector_wheel)
            inspector_canvas.bind(sequence,inspector_wheel)

        search=tk.Frame(center,bg=T.PANEL)
        search.pack(fill='x',padx=13,pady=(15,9))
        T.label(search,'全部字段',font_size=13,bold=True).pack(side='left',padx=(0,15))
        R.RoundedButton(search,text='↺',width=3,command=self.refresh).pack(side='right',padx=(8,0))
        self.search_input=R.RoundedEntry(search,textvariable=self.search_var)
        self.search_input.pack(side='right',fill='x',expand=True)
        T.label(search,'搜索',color=T.FAINT,font_size=9).pack(side='right',padx=(0,8))
        self.search_input.bind('<KeyRelease>',lambda e:self.refresh())
        self.search_input.bind('<Escape>',lambda e:(self.search_var.set(''),self.refresh()))
        self.search_input.bind('<FocusIn>',lambda e:None)
        hint=tk.Frame(center,bg=T.PANEL)
        hint.pack(fill='x',padx=13,pady=(0,12))
        R.RoundedCheck(hint,text='只看已修改',variable=self.show_modified,command=self.refresh).pack(side='left')
        R.RoundedCheck(hint,text='包含对象/数组',variable=self.show_struct,command=self.refresh).pack(side='left',padx=(8,0))
        R.RoundedButton(hint,text='对比存档',command=self.compare_other).pack(side='right')
        R.RoundedButton(hint,text='导出字段 CSV',command=self.export_csv).pack(side='right',padx=(0,8))

        footer=tk.Frame(center,bg=T.PANEL)
        footer.pack(side='bottom',fill='x',padx=13,pady=(10,8))
        self.table_info=T.label(footer,'显示 0 项',color=T.MUTED,font_size=9)
        self.table_info.pack(side='left')
        R.RoundedButton(footer,text='撤销',command=self.undo).pack(side='right',padx=(8,0))
        R.RoundedButton(footer,text='重做',command=self.redo).pack(side='right',padx=(8,0))
        R.RoundedButton(footer,text='恢复全部',style='Danger.TButton',command=self.reset_all).pack(side='right')


        table_card=R.RoundedPanel(center,bg=T.PANEL2,surrounding=T.PANEL,
                                  radius=13,inset=7,border=T.BORDER)
        table_card.pack(fill='both',expand=True,padx=11)
        table=table_card.body
        cols=('field','label','kind','before','now','state')
        self.tree=ttk.Treeview(table,columns=cols,show='headings',selectmode='browse')
        headings={'field':'原始字段路径','label':'说明 / 子项','kind':'类型','before':'载入值','now':'当前值','state':'状态'}
        for key in cols:
            self.tree.heading(key,text=headings[key],command=lambda k=key:self.sort_by(k))
        for key in cols:
            anchor='center' if key in ('kind','state') else 'w'
            self.tree.column(key,width=MIN_WIDTH[key],anchor=anchor,
                             stretch=False,minwidth=MIN_WIDTH[key])
        self.tree.bind('<Configure>',self._fit_table_columns,add='+')
        sb=R.RoundedScrollbar(table,orient='vertical',command=self.tree.yview)
        hb=R.RoundedScrollbar(table,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb.set,xscrollcommand=hb.set)
        self.tree.grid(row=0,column=0,sticky='nsew')
        sb.grid(row=0,column=1,sticky='ns')
        hb.grid(row=1,column=0,sticky='ew')
        table.rowconfigure(0,weight=1)
        table.columnconfigure(0,weight=1)
        self.tree.tag_configure('changed',foreground=T.PINK)
        self.tree.tag_configure('structure',foreground=T.MUTED)
        self.tree.tag_configure('odd',background='#1C1422')
        self.tree.tag_configure('even',background=T.PANEL)
        self.tree.bind('<<TreeviewSelect>>',self.select_item)
        self.tree.bind('<Double-1>',lambda e:self.focus_editor())
        T.label(inspector,'字段详情',font_size=15,bold=True).pack(anchor='w',padx=18,pady=(20,14))
        ttk.Separator(inspector).pack(fill='x',padx=18,pady=(0,17))
        T.label(inspector,textvariable=self.info_title,color=T.PINK,font_size=12,bold=True,wraplength=290,justify='left').pack(anchor='w',padx=18)
        T.label(inspector,textvariable=self.info_path,color=T.FG,font_size=9,wraplength=288,justify='left').pack(anchor='w',padx=18,pady=(5,13))
        T.label(inspector,textvariable=self.info_meta,color=T.MUTED,font_size=9,wraplength=288,justify='left').pack(anchor='w',padx=18,pady=(0,12))
        T.label(inspector,'字段说明',color=T.FAINT,font_size=9).pack(anchor='w',padx=18)
        T.label(inspector,textvariable=self.info_desc,color=T.MUTED,font_size=9,wraplength=287,justify='left').pack(anchor='w',padx=18,pady=(5,16))
        T.label(inspector,'载入时的原始值',color=T.FAINT,font_size=9).pack(anchor='w',padx=18)
        T.label(inspector,textvariable=self.info_old,color=T.FG,font_size=10,wraplength=285,justify='left').pack(anchor='w',padx=18,pady=(5,15))
        T.label(inspector,'编辑当前值',color=T.FAINT,font_size=9).pack(anchor='w',padx=18)
        self.editor_area=tk.Frame(inspector,bg=T.PANEL)
        self.editor_area.pack(fill='x',padx=18,pady=(6,8))
        self.edit_entry=R.RoundedEntry(self.editor_area,textvariable=self.edit_value)
        self.edit_entry.pack(fill='x')
        self.edit_entry.bind('<Return>',lambda e:self.apply_edit())
        self.bool_combo=R.RoundedChoice(self.editor_area,values=['true','false'])
        self.bool_combo.bind('<<ComboboxSelected>>',lambda e:self.edit_value.set(self.bool_combo.get()))
        T.label(inspector,textvariable=self.editor_status,color=T.WARN,font_size=9,wraplength=290,justify='left').pack(anchor='w',padx=18,pady=(0,9))
        R.RoundedButton(inspector,text='应用字段修改',style='Accent.TButton',command=self.apply_edit).pack(fill='x',padx=18,pady=(0,8))
        tools=tk.Frame(inspector,bg=T.PANEL)
        tools.pack(fill='x',padx=18)
        R.RoundedButton(tools,text='恢复该项',command=self.reset_item).pack(side='left',fill='x',expand=True,padx=(0,5))
        R.RoundedButton(tools,text='复制路径',command=self.copy_path).pack(side='left',fill='x',expand=True)
        R.RoundedButton(inspector,text='高级 JSON 结构编辑',command=self.edit_json).pack(fill='x',padx=18,pady=(9,4))
        ttk.Separator(inspector).pack(fill='x',padx=18,pady=(20,14))
        T.label(inspector,'文件操作',color=T.FG,font_size=11,bold=True).pack(anchor='w',padx=18,pady=(0,9))
        R.RoundedCheck(inspector,text='覆盖时自动生成备份',variable=self.backups).pack(anchor='w',padx=18,pady=(0,8))
        R.RoundedButton(inspector,text='写回前校验',command=self.validate).pack(fill='x',padx=18,pady=3)
        R.RoundedButton(inspector,text='查看和恢复备份',command=self.manage_backups).pack(fill='x',padx=18,pady=3)
        R.RoundedButton(inspector,text='导出 / 导入 JSON',command=self.json_menu).pack(fill='x',padx=18,pady=3)
        def bind_inspector_children(widget):
            for child in widget.winfo_children():
                for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):
                    child.bind(sequence,inspector_wheel,add='+')
                bind_inspector_children(child)
        bind_inspector_children(inspector)

        bottom=tk.Frame(self,bg=T.PANEL,height=42,highlightthickness=1,highlightbackground=T.BORDER)
        bottom.pack(fill='x',side='bottom')
        bottom.pack_propagate(False)
        T.label(bottom,textvariable=self.status,color=T.MUTED,font_size=9,anchor='w').pack(anchor='w',padx=20,fill='x',expand=True)

    def _status(self,text):
        self.status.set(text)

    def _error(self,title,e):
        messagebox.showerror(title,str(e),parent=self)
        self._status(f'{title}: {e}')

    def _dirty_confirm(self):
        if not self.session.doc or not self.session.changed_rows():
            return True
        return messagebox.askyesno('未保存修改','当前修改尚未保存。确定丢弃这些更改吗？',parent=self)

    def open_file(self):
        if not self._dirty_confirm():return
        path=filedialog.askopenfilename(parent=self,title='打开 SOL 存档',filetypes=[('Flash SOL files','*.sol'),('All files','*.*')])
        if path:self.open_path(path)

    def open_path(self,path):
        try:
            self.session.open(path)
        except Exception as e:
            self._error('打开失败',e)
            return
        self.category='全部字段'
        self.chosen=None
        self.show_modified.set(False)
        self._update_source()
        self.set_category('全部字段')
        self._status('已读取存档。修改值后点击“应用字段修改”，再保存到 .sol。')

    def _update_source(self):
        if not self.session.doc:return
        doc=self.session.doc
        self.source_info.set(f'文件  {self.session.source_path}     ·     SharedObject: {doc.name}     ·     AMF{doc.amf_version}')

    def auto_find(self):
        if not self._dirty_confirm():return
        files=find_saves()
        if not files:
            messagebox.showinfo('自动查找','未在标准 Flash SharedObject 目录找到目标存档。\n请使用“打开 SOL”手动选择。',parent=self)
            return
        w=self._dialog('发现的存档','960x500')
        shell=tk.Frame(w,bg=T.BG)
        shell.pack(fill='both',expand=True)
        tree,frame=self._dialog_table(shell,[('path','文件路径',690),('time','大小 / 修改时间',220)])
        for i,p in enumerate(files):
            st=p.stat()
            from datetime import datetime
            tree.insert('','end',iid=str(i),values=(str(p),f'{st.st_size} bytes  ·  {datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M}'))
        if files:tree.selection_set('0')
        action_bar=tk.Frame(shell,bg=T.BG)
        action_bar.pack(fill='x',padx=15,pady=(0,15))
        def choose():
            sel=tree.selection()
            if sel:
                p=files[int(sel[0])];w.destroy();self.open_path(p)
        R.RoundedButton(action_bar,text='取消',command=w.destroy).pack(side='right')
        R.RoundedButton(action_bar,text='打开选中存档',style='Accent.TButton',command=choose).pack(side='right',padx=(0,8))
        tree.bind('<Double-1>',lambda e:choose())

    def set_category(self,cat):
        self.category=cat
        for key,btn in self.nav_widgets.items():
            btn.set_selected(key==cat)
        self.refresh()

    def refresh(self,preferred=None):
        self.tree.delete(*self.tree.get_children())
        self.path_by_iid={}
        self.visible=[]
        d=self.session.doc
        if not d:
            for k in ('top','leaf','changed','total'):getattr(self,'stat_'+k).configure(text='—')
            return
        q=self.search_var.get().casefold().strip()
        base=collect_leaves(self.session.baseline.entries) if self.session.baseline else {}
        changed={r['path'] for r in self.session.changed_rows()}
        nodes=list(iter_nodes(d.entries))
        leafs=sum(1 for p,v in nodes if is_leaf(v))
        for key,value in [('top',len(d.entries)),('leaf',leafs),('total',len(nodes)),('changed',len(changed))]:
            getattr(self,'stat_'+key).configure(text=str(value))
        for path,v in nodes:
            leaf=is_leaf(v)
            if not leaf and not self.show_struct.get():continue
            text=path_to_text(path)
            info=get_info(text)
            if self.category!='全部字段' and info.category!=self.category:continue
            if self.show_modified.get() and text not in changed:continue
            current=format_value(v) if leaf else f'<{value_kind(v)}>'
            old=base.get(text)
            before=format_value(old[1]) if old else ('—' if leaf else '<struct>')
            hay=f'{text} {info.label} {info.description} {current} {before} {value_kind(v)}'.casefold()
            if q and q not in hay:continue
            idx=len(self.visible)
            iid=f'r{idx}'
            self.visible.append((path,v))
            self.path_by_iid[iid]=path
            tags=['even' if idx%2==0 else 'odd']
            if text in changed:tags.append('changed')
            if not leaf:tags.append('structure')
            label=info.label.replace(info.label.split(' · ')[0]+' · ','') if ' · ' in info.label else info.label
            self.tree.insert('','end',iid=iid,values=(text,label,value_kind(v),
                before[:85],current[:85],'●' if text in changed else ''),tags=tuple(tags))
        self.table_info.configure(text=f'共 {leafs} 个叶子值  ·  当前显示 {len(self.visible)} 项  ·  更改 {len(changed)} 项')
        self._set_selection(preferred or self.chosen)

    def _set_selection(self,path):
        if not path:return
        for iid,p in self.path_by_iid.items():
            if p==path:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                self.tree.focus(iid)
                self.select_item()
                break

    def _fit_table_columns(self,event=None):
        """Reallocate widths on actual Treeview size, reserving the status column."""
        available=self.tree.winfo_width()
        for key, width in fitted_columns(available).items():
            if int(self.tree.column(key,'width')) != width:
                self.tree.column(key,width=width)

    def sort_by(self,key):
        items=self.tree.get_children('')
        idx=list(self.tree['columns']).index(key)
        rev=getattr(self,'_sort_reverse',False)
        items=sorted(items,key=lambda iid:str(self.tree.item(iid,'values')[idx]).casefold(),reverse=rev)
        for i,item in enumerate(items):self.tree.move(item,'',i)
        self._sort_reverse=not rev

    def select_item(self,event=None):
        if not self.session.doc:return
        sel=self.tree.selection()
        if not sel:return
        path=self.path_by_iid.get(sel[0])
        if path is None:return
        self.chosen=path
        text=path_to_text(path)
        info=get_info(text)
        cur=get_at_path(self.session.doc.entries,path)
        self.info_title.set(info.label)
        self.info_path.set(text)
        self.info_meta.set(f'{info.category}  ·  {value_kind(cur)}  ·  {info.confidence}')
        self.info_desc.set(info.description)
        self.info_current.set(format_value(cur))
        try:old=get_at_path(self.session.baseline.entries,path)
        except:old='(不存在)'
        self.info_old.set(str(format_value(old))[:170])
        self.edit_value.set(format_value(cur) if is_leaf(cur) else '')
        self.editor_status.set('可编辑单项' if is_leaf(cur) else '结构节点：展开子项，或使用高级 JSON')
        if is_leaf(cur) and value_kind(cur)=='bool':
            self.edit_entry.pack_forget()
            self.bool_combo.set(format_value(cur))
            self.bool_combo.pack(fill='x')
        else:
            self.bool_combo.pack_forget()
            self.edit_entry.pack(fill='x')
        if info.bounds and isinstance(cur,(int,float)) and not isinstance(cur,bool):
            self.editor_status.set(f'建议范围 {info.bounds[0]}～{info.bounds[1]}；超出会要求二次确认')

    def focus_editor(self):
        if not self.chosen:return
        if self.bool_combo.winfo_manager():return
        self.edit_entry.focus_set();self.edit_entry.select_range(0,'end')

    def apply_edit(self):
        if not self.session.doc or not self.chosen:return
        path=self.chosen
        current=get_at_path(self.session.doc.entries,path)
        info=get_info(path_to_text(path))
        value_text=self.edit_value.get()
        if value_kind(current)=='bool':value_text=self.bool_combo.get()
        try:
            candidate=parse_user_value(value_text,current)
            if info.bounds and isinstance(candidate,(int,float)) and not isinstance(candidate,bool):
                low,high=info.bounds
                if candidate<low or candidate>high:
                    if not messagebox.askyesno('数值超出建议范围',f'{path_to_text(path)} 的建议范围是 {low}～{high}。\n输入值为 {candidate}。仍要应用吗？',parent=self):return
            changed=self.session.mutate([(path,candidate)])
        except Exception as e:return self._error('无法修改',e)
        self.refresh(path)
        self._status('已在内存中应用修改（尚未保存到文件）。' if changed else '与当前值相同，无需修改。')

    def reset_item(self):
        if not self.chosen:return
        try:self.session.reset_path(self.chosen);self.refresh(self.chosen)
        except Exception as e:self._error('恢复失败',e)

    def reset_all(self):
        if not self.session.doc:return
        if not self.session.changed_rows():return
        if messagebox.askyesno('恢复初始值','恢复本次打开时的所有字段值？可使用 Ctrl+Z 撤销。',parent=self):
            self.session.restore_original();self.refresh();self._status('本次修改已恢复到载入时状态。')

    def undo(self):
        if self.session.doc and self.session.undo():self.refresh();self._status('已撤销。')

    def redo(self):
        if self.session.doc and self.session.redo():self.refresh();self._status('已重做。')

    def copy_path(self):
        if not self.chosen:return
        self.clipboard_clear()
        self.clipboard_append(path_to_text(self.chosen))
        self._status('字段路径已复制。')

    def edit_json(self):
        if not self.session.doc or not self.chosen:return
        p=self.chosen
        v=get_at_path(self.session.doc.entries,p)
        w=self._dialog(f'JSON 结构编辑 / {path_to_text(p)}','860x620')
        txt=tk.Text(w,bg=T.INPUT,fg=T.FG,insertbackground=T.PINK,selectbackground=T.SELECT,
            highlightbackground=T.BORDER,highlightcolor=T.PINK,highlightthickness=1,
            font=(T.MONO,10),undo=True,wrap='none',bd=0,padx=12,pady=12)
        txt.pack(fill='both',expand=True,padx=13,pady=13)
        txt.insert('1.0',json.dumps(to_jsonable(v),ensure_ascii=False,indent=2))
        T.label(w,'高级结构编辑可能改变类型或数组形状；提交前会进行编码往返校验。',color=T.MUTED,font_size=9,bg=T.PANEL).pack(anchor='w',padx=13)
        def apply():
            try:
                from collections import OrderedDict
                from sol_codec import from_jsonable
                obj=from_jsonable(json.loads(txt.get('1.0','end-1c'),object_pairs_hook=OrderedDict))
                self.session.mutate([(p,obj)])
            except Exception as e:return messagebox.showerror('无法应用 JSON',str(e),parent=w)
            w.destroy();self.refresh(p);self._status('JSON 结构已应用；请核对并保存。')
        R.RoundedButton(w,text='验证并应用',style='Accent.TButton',command=apply).pack(anchor='e',padx=13,pady=13)

    def validate(self):
        if not self.session.doc:return
        ok,msg=validate_roundtrip(self.session.doc)
        (messagebox.showinfo if ok else messagebox.showerror)('往返校验',msg,parent=self)
        self._status(msg)

    def save(self):
        if not self.session.doc:return self.open_file()
        if not self.session.source_path:return self.save_as()
        if not self.session.changed_rows():
            self._status('没有待保存修改。')
            return
        if not messagebox.askyesno('覆盖保存',f'写回到原文件？\n\n{self.session.source_path}\n\n请确保游戏已关闭。',parent=self):return
        self._commit(None)

    def save_as(self):
        if not self.session.doc:return
        default=self.session.source_path.name if self.session.source_path else self.session.doc.name+'.sol'
        dest=filedialog.asksaveasfilename(parent=self,title='另存为 SOL',initialfile=default,
                defaultextension='.sol',filetypes=[('Flash SOL files','*.sol')])
        if dest:self._commit(dest)

    def _commit(self,dest):
        try:
            out=self.session.save(dest,backup=self.backups.get())
        except ChangedOnDiskError as e:
            if not messagebox.askyesno('文件已被外部更改',f'{e}\n\n强制覆盖前仍将生成备份。继续吗？',parent=self):return
            try:out=self.session.save(dest,backup=True,force=True)
            except Exception as err:return self._error('保存失败',err)
        except Exception as e:return self._error('保存失败',e)
        self._update_source()
        self.refresh()
        self._status(f'保存成功 · {out.byte_length} bytes · ' + (f'备份：{out.backup}' if out.backup else '新文件'))
        messagebox.showinfo('写回完成',f'已保存并重新解析校验：\n{out.path}\n' + (f'\n自动备份：\n{out.backup}' if out.backup else ''),parent=self)

    def export_csv(self):
        if not self.session.doc:return
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.csv',initialfile='save-fields.csv',filetypes=[('CSV files','*.csv')])
        if not path:return
        base=collect_leaves(self.session.baseline.entries)
        rows=[]
        for p,v in iter_nodes(self.session.doc.entries):
            if not is_leaf(v):continue
            text=path_to_text(p)
            info=get_info(text)
            old=base.get(text)
            rows.append({'path':text,'category':info.category,'label':info.label,'type':value_kind(v),
                'old':format_value(old[1]) if old else '—','new':format_value(v),
                'status':'改变' if old is None or to_jsonable(old[1])!=to_jsonable(v) else '未改'})
        try:export_rows_csv(rows,path)
        except Exception as e:return self._error('CSV 导出失败',e)
        self._status(f'字段 CSV 导出成功：{path}')

    def _dialog(self,title,geometry):
        w=tk.Toplevel(self)
        w.title(title)
        w.geometry(geometry)
        w.minsize(520,260)
        w.configure(bg=T.BG)
        w.transient(self)
        w.grab_set()
        w.after_idle(lambda: R.prefer_rounded_window(w))
        return w

    def _dialog_table(self,w,columns):
        panel=R.RoundedPanel(w,bg=T.PANEL,radius=16,inset=9)
        panel.pack(fill='both',expand=True,padx=15,pady=15)
        frame=panel.body
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        tree=ttk.Treeview(frame,columns=[c[0] for c in columns],show='headings',selectmode='browse')
        for key,label,width in columns:
            tree.heading(key,text=label)
            tree.column(key,width=width,anchor='w')
        bar=R.RoundedScrollbar(frame,orient='vertical',command=tree.yview)
        hbar=R.RoundedScrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=bar.set, xscrollcommand=hbar.set)
        tree.grid(row=0, column=0, sticky='nsew')
        bar.grid(row=0, column=1, sticky='ns')
        hbar.grid(row=1, column=0, sticky='ew')
        return tree,frame

    def compare_other(self):
        if not self.session.doc:return
        path=filedialog.askopenfilename(parent=self,title='选择第二份 SOL 存档以比较',filetypes=[('SOL files','*.sol'),('All','*.*')])
        if not path:return
        try:
            other=load_sol(path)
            if other.name!=self.session.doc.name:
                raise SolError(f'SharedObject 名称不同：{other.name} 和 {self.session.doc.name}')
            rows=describe_diff(other,self.session.doc)
        except Exception as e:return self._error('比较失败',e)
        w=self._dialog('双存档差异比较','1200x730')
        T.label(w,f'对照：{Path(path).name}  →  当前内存     ·     变化 {len(rows)} 个叶子字段',color=T.FG,bold=True).pack(anchor='w',padx=15,pady=(15,0))
        tree,_=self._dialog_table(w,[('path','字段路径',295),('cat','分类',130),('old','对照值',180),('new','当前值',180),('status','变更',80)])
        for i,row in enumerate(rows):tree.insert('','end',iid=str(i),values=(row['path'],row['category'],row['old'],row['new'],row['status']))
        bar=tk.Frame(w,bg=T.PANEL)
        bar.pack(fill='x',padx=15,pady=(0,15))
        def export():
            dst=filedialog.asksaveasfilename(parent=w,defaultextension='.csv',initialfile='save-diff.csv',filetypes=[('CSV','*.csv')])
            if dst:
                try:export_rows_csv(rows,dst);messagebox.showinfo('已导出',dst,parent=w)
                except Exception as e:messagebox.showerror('导出失败',str(e),parent=w)
        R.RoundedButton(bar,text='导出差异 CSV',command=export).pack(side='right')
        R.RoundedButton(bar,text='关闭',command=w.destroy).pack(side='right',padx=(0,8))

    def json_menu(self):
        if not self.session.doc:return
        w=self._dialog('JSON 导入 / 导出','470x205')
        T.label(w,'使用本工具的结构化 JSON 格式',color=T.FG,bold=True,font_size=12).pack(anchor='w',padx=20,pady=(18,15))
        btns=tk.Frame(w,bg=T.PANEL)
        btns.pack(fill='x',padx=20)
        def export():
            w.destroy()
            p=filedialog.asksaveasfilename(parent=self,defaultextension='.json',filetypes=[('JSON','*.json')])
            if p:
                try:self.session.export_json(p);self._status(f'JSON 已导出：{p}')
                except Exception as e:self._error('导出失败',e)
        def imp():
            w.destroy()
            p=filedialog.askopenfilename(parent=self,filetypes=[('JSON','*.json')])
            if p:
                if not messagebox.askyesno('导入 JSON','这会替换当前内存中的字段树（仍可撤销）。继续吗？',parent=self):return
                try:self.session.import_json(p);self.refresh();self._status('已导入 JSON 到内存。')
                except Exception as e:self._error('导入失败',e)
        R.RoundedButton(btns,text='导出 JSON',command=export).pack(side='left',fill='x',expand=True,padx=(0,8))
        R.RoundedButton(btns,text='导入 JSON',command=imp,style='Accent.TButton').pack(side='left',fill='x',expand=True)
        T.label(w,'仅在保存 .sol 后才会修改游戏存档。',color=T.MUTED,font_size=9).pack(anchor='w',padx=20,pady=14)

    def manage_backups(self):
        if not self.session.source_path:return
        source=self.session.source_path
        root=source.parent/'SOLSaveEditor_Backups'
        backups=sorted(root.glob(f'{source.stem}.*.sol.bak'),reverse=True) if root.is_dir() else []
        if not backups:return messagebox.showinfo('备份管理','当前文件没有找到由本工具建立的备份。',parent=self)
        w=self._dialog('自动备份管理','1060x520')
        tree,_=self._dialog_table(w,[('path','备份文件',730),('size','大小',110)])
        for i,p in enumerate(backups):tree.insert('','end',iid=str(i),values=(str(p),p.stat().st_size))
        tree.selection_set('0')
        def restore():
            sel=tree.selection()
            if not sel:return
            p=backups[int(sel[0])]
            if not messagebox.askyesno('确认恢复备份',f'恢复到：\n{source}\n\n选中备份：\n{p}\n\n将自动再次备份当前文件。建议先关闭游戏。',parent=w):return
            try:
                from editor_core import EditorSession
                temp=EditorSession();temp.open(p)
                if temp.doc.name!=self.session.doc.name:raise SolError('备份与原存档 SharedObject 名称不一致。')
                temp.save(source,backup=True)
                self.session.open(source)
            except Exception as e:return messagebox.showerror('恢复失败',str(e),parent=w)
            w.destroy();self.refresh();self._update_source();self._status('备份已恢复并验证。')
        R.RoundedButton(w,text='恢复选中备份',style='Accent.TButton',command=restore).pack(pady=(0,14))

    def _close(self):
        if self._dirty_confirm():self.destroy()


def cli():
    p=argparse.ArgumentParser(description='Flash SharedObject AMF3 save editor')
    p.add_argument('file',nargs='?',help='SOL file to open')
    p.add_argument('--validate',action='store_true',help='check input and AMF3 roundtrip without GUI')
    p.add_argument('--diff',metavar='OTHER',help='compare with another SOL file without GUI')
    args=p.parse_args()
    if args.validate or args.diff:
        if not args.file:p.error('a file argument is required')
        try:
            doc=load_sol(args.file)
            if args.validate:
                ok,msg=validate_roundtrip(doc)
                print(msg)
                print(f'SharedObject: {doc.name} | AMF{doc.amf_version} | fields={len(doc.entries)} | leaves={len(collect_leaves(doc.entries))}')
                return 0 if ok else 2
            other=load_sol(args.diff)
            rows=describe_diff(other,doc)
            for row in rows:print(f"{row['status']:6}  {row['path']:<40}  {row['old']} -> {row['new']}")
            print('Changed leaf fields:',len(rows))
            return 0
        except Exception as e:
            print('ERROR:',e,file=sys.stderr)
            return 1
    SaveEditor(args.file).mainloop()
    return 0


if __name__=='__main__':
    sys.exit(cli())
