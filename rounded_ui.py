"""Canvas-rendered rounded widgets for the dark-pink Tkinter UI.

These widgets do not depend on an extra UI framework. All corner radii are
physical Canvas geometry; none rely on ttk themes pretending to be rounded.
"""
from __future__ import annotations

import math
import tkinter as tk
from tkinter import font as tkfont

import theme as C


def round_rect(canvas: tk.Canvas, x1, y1, x2, y2, radius=14, *, fill, outline='', width=1, tags=()):
    """Draw a filled rounded rectangle using explicit quarter-circle vertices."""
    r = max(0.0, min(float(radius), (x2-x1)/2, (y2-y1)/2))
    points = []
    for cx, cy, a0 in ((x2-r,y1+r,-90), (x2-r,y2-r,0),
                        (x1+r,y2-r,90), (x1+r,y1+r,180)):
        for j in range(9):
            a = math.radians(a0+j*90/8)
            points.extend((cx + r*math.cos(a), cy + r*math.sin(a)))
    if not points:
        return None
    return canvas.create_polygon(points, fill=fill, outline=outline, width=width,
                                 smooth=False, tags=tags, joinstyle=tk.ROUND)


class RoundedPanel(tk.Canvas):
    """A real rounded card containing a normal Tk frame (``.body``)."""
    def __init__(self, parent, *, width=300, height=240, bg=C.PANEL,
                 surrounding=C.BG, radius=19, inset=11, border=C.BORDER):
        super().__init__(parent, bg=surrounding, bd=0, highlightthickness=0,
                         relief='flat', width=width, height=height)
        self.surface = bg
        self.radius = radius
        self.border = border
        self.inset = inset
        self.body = tk.Frame(self, bg=bg, bd=0, highlightthickness=0)
        self._window = self.create_window(inset, inset, anchor='nw', window=self.body)
        self.bind('<Configure>', self._draw)

    def _draw(self, event=None):
        w = self.winfo_width() if event is None else event.width
        h = self.winfo_height() if event is None else event.height
        self.delete('background')
        round_rect(self, 1, 1, max(2,w-2), max(2,h-2), self.radius,
                   fill=self.surface, outline=self.border, width=1, tags=('background',))
        self.tag_lower('background')
        self.coords(self._window, self.inset, self.inset)
        self.itemconfigure(self._window,
                           width=max(1,w-2*self.inset), height=max(1,h-2*self.inset))


class RoundedButton(tk.Canvas):
    """Clickable/keyboard-accessible rounded button with an intrinsic width."""
    def __init__(self, parent, *, text, command, style='', width=None, height=39):
        self.text = text
        self.command = command
        self.style_name = style
        self._hover = False
        self._pressed = False
        self._font = tkfont.Font(family=C.FONT, size=10,
                                 weight='bold' if style=='Accent.TButton' else 'normal')
        natural_w = max(43, self._font.measure(str(text)) + 32)
        if width is not None:
            natural_w = max(natural_w, int(width)*11 + 13)
        super().__init__(parent, width=natural_w, height=height, bd=0,
                         highlightthickness=0, bg=self._parent_bg(parent),
                         relief='flat', cursor='hand2', takefocus=True)
        self.bind('<Configure>', self._draw)
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<ButtonPress-1>', self._down)
        self.bind('<ButtonRelease-1>', self._up)
        self.bind('<space>', self._key)
        self.bind('<Return>', self._key)
        self.bind('<FocusIn>', self._draw)
        self.bind('<FocusOut>', self._draw)

    @staticmethod
    def _parent_bg(parent):
        try: return parent.cget('bg')
        except tk.TclError: return C.PANEL

    def _enter(self, _=None):
        self._hover=True;self._draw()

    def _leave(self, _=None):
        self._hover=False;self._pressed=False;self._draw()

    def _down(self, _=None):
        self._pressed=True;self.focus_set();self._draw()

    def _up(self, event):
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        fire = self._pressed and inside
        self._pressed=False;self._draw()
        if fire and self.command: self.command()

    def _key(self, _=None):
        if self.command:self.command()
        return 'break'

    def _draw(self, _=None):
        w,h=self.winfo_width(),self.winfo_height()
        if w <= 1 or h <= 1: return
        self.delete('all')
        accent=self.style_name=='Accent.TButton'
        if accent:
            bg = '#B85084' if self._pressed else (C.PINK if self._hover else C.PINK2)
            fg='#160A14'
        else:
            bg=C.SELECT if self._pressed else (C.HOVER if self._hover else C.PANEL2)
            fg=C.WARN if self.style_name=='Danger.TButton' else C.FG
        round_rect(self, 1, 1, w-2, h-2, 12,
                   fill=bg, outline=C.PINK if self.focus_get() is self else (bg if accent else C.BORDER))
        self.create_text(w/2,h/2, text=self.text,fill=fg,font=self._font,
                         anchor='center',width=max(1,w-16))


class RoundedNav(tk.Canvas):
    def __init__(self,parent,text,command):
        super().__init__(parent, height=37, bg=C.PANEL, highlightthickness=0,
                         cursor='hand2', bd=0)
        self.text=text;self.command=command
        self.selected=False;self.hover=False
        self.bind('<Configure>',self._draw)
        self.bind('<Enter>',lambda e:self._set_hover(True))
        self.bind('<Leave>',lambda e:self._set_hover(False))
        self.bind('<Button-1>',lambda e:self.command())

    def _set_hover(self,flag):
        self.hover=flag;self._draw()

    def set_selected(self,selected):
        self.selected=selected;self._draw()

    def _draw(self,_=None):
        self.delete('all')
        w,h=self.winfo_width(),self.winfo_height()
        if w<3 or h<3:return
        bg=C.SELECT if self.selected else (C.HOVER if self.hover else C.PANEL)
        round_rect(self,1,1,w-2,h-2,10,fill=bg,outline='')
        if self.selected:
            round_rect(self,4,10,7,h-10,2,fill=C.PINK2,outline='')
        self.create_text(16,h/2,text=self.text,fill=C.PINK if self.selected else C.MUTED,
                         anchor='w',font=(C.FONT,10),width=max(1,w-30))


class RoundedEntry(tk.Frame):
    """A round entry shell with an actual editable Tk Entry, not fake text."""
    def __init__(self,parent,*,textvariable=None,width=190):
        super().__init__(parent,bg=self._parent_bg(parent),height=42,width=width)
        self.pack_propagate(False)
        self.canvas=tk.Canvas(self,bg=self.cget('bg'),bd=0,highlightthickness=0)
        self.canvas.pack(fill='both',expand=True)
        self.entry=tk.Entry(self.canvas,textvariable=textvariable,bg=C.INPUT,fg=C.FG,
                            insertbackground=C.PINK,selectbackground=C.SELECT,
                            selectforeground=C.FG,relief='flat',bd=0,
                            font=(C.FONT,10),highlightthickness=0)
        self._win=self.canvas.create_window(13,9,anchor='nw',window=self.entry)
        self._focused=False
        self.canvas.bind('<Configure>',self._draw)
        self.entry.bind('<FocusIn>',lambda e:self._focus(True),add='+')
        self.entry.bind('<FocusOut>',lambda e:self._focus(False),add='+')
        self.canvas.bind('<Button-1>',lambda e:self.entry.focus_set())

    @staticmethod
    def _parent_bg(parent):
        try:return parent.cget('bg')
        except tk.TclError:return C.PANEL

    def _focus(self,flag):
        self._focused=flag;self._draw()

    def _draw(self,_=None):
        w,h=self.canvas.winfo_width(),self.canvas.winfo_height()
        if w<2 or h<2:return
        self.canvas.delete('background')
        round_rect(self.canvas,1,1,w-2,h-2,12,fill=C.INPUT,
                   outline=C.PINK if self._focused else C.BORDER,tags=('background',))
        self.canvas.tag_lower('background')
        self.canvas.coords(self._win,13,max(2,(h-26)//2))
        self.canvas.itemconfigure(self._win,width=max(1,w-26),height=26)

    def bind(self,sequence=None,func=None,add=None):
        if sequence in ('<Return>','<Escape>','<KeyRelease>','<KeyPress>') and hasattr(self,'entry'):
            return self.entry.bind(sequence,func,add)
        return super().bind(sequence,func,add)

    def focus_set(self):self.entry.focus_set()
    def select_range(self,first,last):self.entry.select_range(first,last)


class RoundedChoice(tk.Canvas):
    """A two-option pill/segmented control in place of a square popup combobox."""
    def __init__(self,parent,*,values=('true','false')):
        super().__init__(parent,bg=self._parent_bg(parent),height=42,
                         highlightthickness=0,bd=0,cursor='hand2')
        self.values=tuple(values)
        self.current=self.values[0]
        self.bind('<Configure>',self._draw)
        self.bind('<Button-1>',self._clicked)

    @staticmethod
    def _parent_bg(parent):
        try:return parent.cget('bg')
        except tk.TclError:return C.PANEL

    def get(self):return self.current
    def set(self,value):
        if str(value) in self.values:
            self.current=str(value)
        self._draw()

    def _clicked(self,e):
        width=max(1,self.winfo_width())
        i=min(len(self.values)-1,max(0,int(e.x/(width/len(self.values)))))
        self.set(self.values[i])
        self.event_generate('<<ComboboxSelected>>')

    def _draw(self,_=None):
        self.delete('all')
        w,h=self.winfo_width(),self.winfo_height()
        if w<2 or h<2:return
        round_rect(self,1,1,w-2,h-2,12,fill=C.INPUT,outline=C.BORDER)
        count=len(self.values)
        item_w=(w-6)/count
        for i,item in enumerate(self.values):
            x1=3+i*item_w;x2=3+(i+1)*item_w
            selected=self.current==item
            if selected:round_rect(self,x1,3,x2,h-3,10,fill=C.SELECT,outline=C.PINK2)
            self.create_text((x1+x2)/2,h/2,text=item,
                             fill=C.PINK if selected else C.MUTED,font=(C.FONT,10,'bold' if selected else 'normal'))


class RoundedCheck(tk.Canvas):
    """Compact iOS-like round switch plus label, wired to a Tk BooleanVar."""
    def __init__(self,parent,*,text,variable,command=None):
        font=tkfont.Font(family=C.FONT,size=9)
        width=48+font.measure(text)+15
        super().__init__(parent,width=width,height=30,bg=self._parent_bg(parent),
                         highlightthickness=0,bd=0,cursor='hand2')
        self.text=text;self.variable=variable;self.command=command
        self.bind('<Configure>',self._draw)
        self.bind('<Button-1>',self._toggle)
        self.variable.trace_add('write',lambda *_:self._draw())

    @staticmethod
    def _parent_bg(parent):
        try:return parent.cget('bg')
        except tk.TclError:return C.PANEL

    def _toggle(self,_):
        self.variable.set(not self.variable.get())
        if self.command:self.command()

    def _draw(self,_=None):
        self.delete('all')
        on=bool(self.variable.get())
        round_rect(self,1,5,39,25,10,fill=C.PINK2 if on else C.INPUT,outline=C.PINK2 if on else C.BORDER)
        round_rect(self,22 if on else 3,7,37 if on else 18,23,8,fill=C.FG,outline='')
        self.create_text(48,15,text=self.text,anchor='w',fill=C.FG,font=(C.FONT,9))


class RoundedScrollbar(tk.Canvas):
    """Arrowless rounded thumb with native Tk yview/xview command semantics."""
    def __init__(self,parent,*,orient='vertical',command=None):
        self.vertical=orient=='vertical'
        super().__init__(parent,width=12 if self.vertical else 90,
                         height=90 if self.vertical else 12,
                         bg=self._parent_bg(parent),bd=0,highlightthickness=0,
                         cursor='hand2')
        self.command=command
        self.first=0.0;self.last=1.0
        self.hover=False;self.drag=None
        self.bind('<Configure>',self._draw)
        self.bind('<Enter>',lambda e:self._hover(True))
        self.bind('<Leave>',lambda e:self._hover(False))
        self.bind('<ButtonPress-1>',self._press)
        self.bind('<B1-Motion>',self._motion)
        self.bind('<ButtonRelease-1>',lambda e:setattr(self,'drag',None))

    @staticmethod
    def _parent_bg(parent):
        try:return parent.cget('bg')
        except tk.TclError:return C.PANEL

    def _hover(self,value):self.hover=value;self._draw()

    def set(self,first,last):
        try:self.first=float(first);self.last=float(last)
        except (ValueError,TypeError):return
        self._draw()

    def _thumb(self):
        size=self.winfo_height() if self.vertical else self.winfo_width()
        track=max(1,size-8)
        fraction=max(0.0,min(1.0,self.last-self.first))
        length=min(track,max(26,track*fraction))
        offset=(track-length)*min(1,max(0,self.first/max(0.000001,1-fraction)))
        return 4+offset,4+offset+length

    def _coord(self,event):return event.y if self.vertical else event.x

    def _press(self,event):
        if self.last-self.first>=0.999999:return
        a,b=self._thumb();p=self._coord(event)
        if a<=p<=b:
            self.drag=p-a
        else:
            self.drag=(b-a)/2
            self._move_to(p)

    def _motion(self,event):
        if self.drag is not None:self._move_to(self._coord(event))

    def _move_to(self,pos):
        if self.command is None:return
        a,b=self._thumb()
        size=self.winfo_height() if self.vertical else self.winfo_width()
        usable=max(1,size-8-(b-a))
        fraction=max(0.0,min(1.0,self.last-self.first))
        relative=max(0.0,min(1.0,(pos-self.drag-4)/usable))
        self.command('moveto',relative*(1-fraction))

    def _draw(self,_=None):
        self.delete('all')
        w,h=self.winfo_width(),self.winfo_height()
        if w<2 or h<2:return
        if self.last-self.first>=0.999999:return
        a,b=self._thumb()
        if self.vertical:
            round_rect(self,2,a,w-2,b,min(5,(b-a)/2),fill=C.SELECT if self.hover else C.HOVER,outline='')
        else:
            round_rect(self,a,2,b,h-2,min(5,(b-a)/2),fill=C.SELECT if self.hover else C.HOVER,outline='')

class RoundedBadge(tk.Canvas):
    """Rounded brand icon using the same accent colors as the rest of the UI."""
    def __init__(self,parent,text='S',size=46):
        super().__init__(parent,width=size,height=size,bd=0,highlightthickness=0,
                         bg=self._parent_bg(parent))
        self.text=text
        self.bind('<Configure>',self._draw)

    @staticmethod
    def _parent_bg(parent):
        try:return parent.cget('bg')
        except tk.TclError:return C.BG

    def _draw(self,event=None):
        self.delete('all')
        w,h=self.winfo_width(),self.winfo_height()
        if w<2 or h<2:return
        round_rect(self,1,1,w-2,h-2,13,fill=C.PINK2,outline='')
        self.create_text(w/2,h/2,text=self.text,font=(C.FONT,20,'bold'),fill='#220A1B')


def prefer_rounded_window(window):
    """Ask Windows 11 DWM for rounded native window corners when supported."""
    import sys
    if sys.platform != 'win32':return
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        option = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 33, ctypes.byref(option), ctypes.sizeof(option))
    except (OSError, AttributeError, ValueError):
        pass
