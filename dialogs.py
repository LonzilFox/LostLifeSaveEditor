"""Application-owned dark pink modal dialogs (native file dialogs follow Windows)."""
from __future__ import annotations
import tkinter as tk
import math
from tkinter import ttk, font as tkfont
import theme as T
import rounded_ui as R


class PinkDialogs:
    def _modal(self, title, text, parent=None, kind='info'):
        root=parent or tk._default_root
        if root is None:
            raise RuntimeError('No Tk root for dialog')
        win=tk.Toplevel(root)
        win.title(title)
        win.configure(bg=T.PANEL)
        msg_font=tkfont.Font(root=root,family=T.FONT,size=10)
        line_count=sum(max(1,math.ceil(msg_font.measure(line or ' ')/390)) for line in str(text).splitlines())
        height=max(270,min(560,165+line_count*25))
        win.geometry(f'540x{height}')
        win.minsize(460,260)
        win.transient(root)
        win.resizable(True,True)
        win.grab_set()
        win.after_idle(lambda: R.prefer_rounded_window(win))
        res={'value': False}
        icon='!' if kind=='error' else ('?' if kind=='ask' else 'i')
        icon_color=T.WARN if kind=='error' else T.PINK
        card=R.RoundedPanel(win,bg=T.PANEL,surrounding=T.PANEL,radius=18,inset=12)
        card.pack(fill='both',expand=True,padx=10,pady=10)
        frame=card.body
        frame.configure(padx=10,pady=10)
        row=tk.Frame(frame,bg=T.PANEL)
        row.pack(fill='both',expand=True)
        symbol=tk.Canvas(row,bg=T.PANEL,highlightthickness=0,bd=0,width=44,height=44)
        symbol.pack(side='left',anchor='n',padx=(0,14))
        R.round_rect(symbol,1,1,43,43,12,fill=T.SELECT,outline='')
        symbol.create_text(22,22,text=icon,fill=icon_color,font=(T.FONT,19,'bold'))
        msg=tk.Frame(row,bg=T.PANEL)
        msg.pack(side='left',fill='both',expand=True)
        T.label(msg,title,color=T.FG,bold=True,font_size=13).pack(anchor='w',pady=(0,9))
        T.label(msg,text,color=T.MUTED,font_size=10,wraplength=390,justify='left',anchor='nw').pack(fill='both',expand=True)
        bar=tk.Frame(frame,bg=T.PANEL)
        bar.pack(fill='x',pady=(10,0))
        def done(value):
            res['value']=value
            win.destroy()
        if kind=='ask':
            R.RoundedButton(bar,text='确定',style='Accent.TButton',command=lambda:done(True)).pack(side='right')
            R.RoundedButton(bar,text='取消',command=lambda:done(False)).pack(side='right',padx=(0,8))
        else:
            R.RoundedButton(bar,text='确定',style='Accent.TButton',command=lambda:done(True)).pack(side='right')
        win.bind('<Escape>',lambda e:done(False))
        if kind=='ask':win.bind('<Return>',lambda e:done(True))
        win.protocol('WM_DELETE_WINDOW',lambda:done(False))
        win.update_idletasks()
        x=root.winfo_rootx()+max(0,(root.winfo_width()-win.winfo_width())//2)
        y=root.winfo_rooty()+max(0,(root.winfo_height()-win.winfo_height())//2)
        win.geometry(f'+{x}+{y}')
        win.wait_window()
        return res['value']

    def showerror(self,title,message,parent=None,**kwargs):
        return self._modal(title,str(message),parent,'error')
    def showinfo(self,title,message,parent=None,**kwargs):
        return self._modal(title,str(message),parent,'info')
    def askyesno(self,title,message,parent=None,**kwargs):
        return self._modal(title,str(message),parent,'ask')

messagebox=PinkDialogs()
