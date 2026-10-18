"""Pink / near-black palette shared by every Tk and ttk control."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk

BG='#0C0910'
PANEL='#17101D'
PANEL2='#211627'
INPUT='#291C32'
HOVER='#37243F'
PINK='#F08AB7'
PINK2='#D8679B'
SELECT='#553048'
BORDER='#473044'
FG='#F9EAF2'
MUTED='#BCA9BA'
FAINT='#8C778A'
SUCCESS='#8ED7B7'
WARN='#F3C68D'

FONT='Microsoft YaHei UI'
MONO='Consolas'


def _configure_scrollbars(sty: ttk.Style):
    # Remove arrow buttons for a cleaner, more iOS-like slim scrollbar.
    try:
        sty.layout('Slim.Vertical.TScrollbar', [
            ('Vertical.Scrollbar.trough', {'sticky': 'ns', 'children': [
                ('Vertical.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})
            ]})
        ])
        sty.layout('Slim.Horizontal.TScrollbar', [
            ('Horizontal.Scrollbar.trough', {'sticky': 'we', 'children': [
                ('Horizontal.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})
            ]})
        ])
    except tk.TclError:
        pass

    for name in ('Slim.Vertical.TScrollbar', 'Slim.Horizontal.TScrollbar'):
        sty.configure(
            name,
            background=HOVER,
            troughcolor=PANEL2,
            bordercolor=PANEL2,
            arrowcolor=PINK,
            lightcolor=PANEL2,
            darkcolor=PANEL2,
            relief='flat',
            width=10,
            gripcount=0,
            arrowsize=0,
        )
        sty.map(name, background=[('active', SELECT), ('pressed', PINK2)])


def apply(root:tk.Misc):
    sty=ttk.Style(root)
    sty.theme_use('clam')
    root.option_add('*Font', (FONT, 10))
    root.option_add('*Listbox.background', INPUT)
    root.option_add('*Listbox.foreground', FG)
    root.option_add('*Listbox.selectBackground', SELECT)
    root.option_add('*Listbox.selectForeground', FG)
    root.option_add('*Menu.background', PANEL2)
    root.option_add('*Menu.foreground', FG)
    root.option_add('*Menu.activeBackground', SELECT)
    root.option_add('*Menu.activeForeground', FG)
    # Combobox popdown listbox styling on Windows ttk.
    root.option_add('*TCombobox*Listbox.background', INPUT)
    root.option_add('*TCombobox*Listbox.foreground', FG)
    root.option_add('*TCombobox*Listbox.selectBackground', SELECT)
    root.option_add('*TCombobox*Listbox.selectForeground', FG)
    root.option_add('*TCombobox*Listbox.font', (FONT, 10))

    sty.configure('TFrame', background=BG)
    sty.configure('Panel.TFrame', background=PANEL)
    sty.configure('Inner.TFrame', background=PANEL2)
    sty.configure('TLabel', background=BG, foreground=FG, font=(FONT,10))
    sty.configure('Panel.TLabel', background=PANEL, foreground=FG, font=(FONT,10))
    sty.configure('Small.TLabel', background=PANEL, foreground=MUTED, font=(FONT,9))

    sty.configure('TButton', background=PANEL2, foreground=FG, bordercolor=BORDER, borderwidth=1,
                  relief='flat', focuscolor=PANEL2, padding=(14,10), font=(FONT,10))
    sty.map('TButton', background=[('pressed',SELECT), ('active',HOVER)], foreground=[('disabled',FAINT)])
    sty.configure('Accent.TButton', background=PINK2, foreground='#160A14', bordercolor=PINK,
                  borderwidth=1, padding=(16,10), font=(FONT,10,'bold'))
    sty.map('Accent.TButton',background=[('pressed','#B85084'),('active',PINK)],foreground=[('active','#160A14')])
    sty.configure('Danger.TButton', background=PANEL2, foreground=WARN, bordercolor=BORDER, padding=(14,10))
    sty.map('Danger.TButton',background=[('active',HOVER)])

    sty.configure('TEntry', fieldbackground=INPUT, foreground=FG, background=INPUT,
                  insertcolor=FG, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                  padding=(12,10), relief='flat', font=(FONT,10))
    sty.map('TEntry', fieldbackground=[('disabled',PANEL2),('readonly',INPUT)],
            foreground=[('disabled',FAINT)], bordercolor=[('focus',PINK)])

    sty.configure('TCombobox', fieldbackground=INPUT, background=INPUT, foreground=FG,
                  arrowcolor=PINK, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                  padding=(12,10), font=(FONT,10), selectbackground=SELECT, selectforeground=FG)
    sty.map('TCombobox', fieldbackground=[('readonly',INPUT),('focus',INPUT)],
            foreground=[('readonly',FG)], background=[('active',HOVER)], bordercolor=[('focus',PINK)])

    sty.configure('TCheckbutton',background=PANEL,foreground=FG,font=(FONT,9),indicatorbackground=INPUT,
                  indicatormargin=5, focuscolor=PANEL)
    sty.map('TCheckbutton',background=[('active',PANEL)], foreground=[('disabled',FAINT)],
            indicatorbackground=[('selected',PINK2)], indicatorcolor=[('selected',PINK)])

    sty.configure('Treeview',background=PANEL,fieldbackground=PANEL,foreground=FG,
                  bordercolor=BORDER,lightcolor=PANEL,darkcolor=PANEL,
                  rowheight=35,relief='flat', font=(FONT,9))
    sty.map('Treeview',background=[('selected',SELECT)],foreground=[('selected',FG)])
    sty.configure('Treeview.Heading',background=PANEL2,foreground=MUTED,font=(FONT,9,'bold'),
                  bordercolor=BORDER,borderwidth=1,padding=(9,10),relief='flat')
    sty.map('Treeview.Heading',background=[('active',HOVER)])

    sty.configure('TScrollbar', background=HOVER,troughcolor=PANEL2,
                  bordercolor=PANEL2,arrowcolor=PINK, lightcolor=PANEL2,darkcolor=PANEL2, width=11)
    sty.map('TScrollbar', background=[('active',SELECT),('pressed',PINK2)])
    _configure_scrollbars(sty)

    sty.configure('TPanedwindow',background=BORDER)
    sty.configure('TSeparator',background=BORDER)
    return sty


def label(parent, text='', color=FG, font_size=10, bold=False, bg=PANEL, **kwargs):
    return tk.Label(parent,text=text,bg=bg,fg=color,font=(FONT,font_size,'bold' if bold else 'normal'),**kwargs)


def nav_button(parent,text,command):
    b=tk.Button(parent,text=text,command=command,bg=PANEL,fg=MUTED,activebackground=HOVER,
        activeforeground=FG,relief='flat',bd=0,anchor='w',padx=16,pady=11,
        highlightthickness=0,cursor='hand2',font=(FONT,10))
    return b
