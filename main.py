#!/usr/bin/python
import os, sys, re, shutil, pickle

base_dir = os.path.dirname(__file__)
if base_dir == '': base_dir = '.'

class Action:
    def __init__(self, quest, aid, s, msg, stack):
        self.loc_id = aid if '=*' in s else None
        if self.loc_id: quest.locations[self.loc_id] = ''
        condition = [x[1:-1].split(',') for x in re.findall(r'\([^\(\)]*\)', s[:s.find('*')])]
        extra = [x for x in stack if x in quest.locations][-1:] + stack[-1:]
        if len(extra) == len(stack[-1:]): extra.append('!__')
        self.action = s[s.find('*')+1:].strip()
        key = re.search(r'([^)=]*)=?\*', s).groups()[0].strip()
        if key:
            key = '__' + '__'.join(extra) + '_@' + key
            extra.append('!' + key)
            msg += '()/+%s/' % key
        self.msg = msg
        self.condition = [x+extra for x in condition] if condition!=[] else [extra]

class QuestEngine:
    def __init__(self):
        self.title, self.res, self.loc_msg = None, '', ''
        self.files = [os.path.join(base_dir, x) for x in os.listdir(base_dir) if x.endswith('.qst')]
        self.alternatives = [open(f).readline().strip() for f in self.files]
        self.locations = {}
        self.actions, self.stack, self.items = [], [], []
        self.loc, self.new_loc = None, True

    def parse_quest(self, filename):
        group, groups = [], []
        try: lines = open(filename, encoding='utf8').readlines()
        except Exception: lines = [x.decode('utf8') for x in open(filename).readlines()]
        for l in lines:
            if l.strip() == '':
                if len(group) > 0: groups.append(group)
                group = []
            else: group.append(l)
        if len(group) > 0: groups.append(group)
        self.title = ' '.join(groups[0])
        action_id = 0
        for i in range(1, len(groups)):
            s = groups[i][0].replace('\t', '    ')
            level = 0
            while s.startswith('    '): level, s = level+1, s[4:]
            s = s.strip()
            text = ' '.join([l.strip() for l in groups[i][1:]]) + ('()/+___%d/' % i if ('*' in s) and ('=*' not in s) else '')
            if '*' not in s:
                if level > 0: raise Exception('Incorrect indentation')
                if self.loc is None: self.loc = '_'+s
                self.locations['_'+s], self.stack = text, ['_'+s]
                continue
            self.actions.append(Action(self, '___%d' % i, s, text, self.stack[:level]))
            self.stack = self.stack[:level] + ['___%d' % i]
        self.stack = [self.loc]

    def cond(self, x):
        for c in x:
            ok = True
            for sv in [v.strip() for v in c]:
                if sv!='' and ok: ok = (sv in self.litems) or (sv[0]=='!' and (sv[1:] not in self.litems))
            if ok: return True
        return False
    
    def handle_message(self, msg):
        res = ''
        ok = True
        for p in re.split(r'(?!\\)(\([^\)]*\)|/[^/]*/)', msg):
            if (len(p) > 0) and p[0] == '(':
                ok = self.cond([p[1:-1].split(',')])
            elif ok:
                if (len(p) > 0) and p[0] == '/':
                    for r in [x.strip() for x in p[1:-1].split(',')]:
                        if r[0] == '+': self.items.append(r[1:])
                        elif r[0] == '-' and r[1:] in self.items: self.items.remove(r[1:])
                        elif r == '=-': self.loc, self.stack, self.new_loc = self.stack[-1], self.stack[:-1], True
                        elif r[0] == '=': self.loc, self.stack, self.new_loc = '_'+r[1:], ['_'+r[1:]], True
                        elif r == '%': res += ', '.join([x for x in self.items if x[0] != '_'])
                else: res += p
        res = res.replace('\\/', '/').replace('\\(', '(').replace('\\)', ')').strip()
        return res.replace('\\\\', '\n')

    def action(self, n):
        if (self.loc in self.locations) and self.loc[:2]!='__':
            self.loc_msg = self.handle_message(self.locations[self.loc])
        else:
            self.loc_msg = ''
        self.new_loc = not self.title
        if not self.title: self.parse_quest(self.files[n])
        else:
            if self.lactions[n].loc_id: self.loc, self.stack = self.lactions[n].loc_id, self.stack + [self.loc]
            self.res = self.handle_message(self.lactions[n].msg)

        self.litems = self.items + [self.stack[0][1:], self.loc]
        if len([x for x in self.items if x[0] != '_']) > 0: self.litems.append('%')
        if self.loc.startswith('__'): self.litems.append('__')
        if (self.loc in self.locations) and self.loc[:2]!='__':
            if self.new_loc: self.loc_msg = self.handle_message(self.locations[self.loc])
        else:
            self.loc_msg = ''
        self.lactions = [a for a in self.actions if self.cond(a.condition) and self.loc != a.loc_id]
        self.alternatives = [x.action for x in self.lactions]
        pickle.dump(self, open(os.path.join(base_dir, 'autosave'), 'wb'))

if __name__ == "__main__":
    try: quest = pickle.load(open(os.path.join(base_dir, 'autosave'), 'rb'))
    except Exception: quest = QuestEngine()

try:
    if len(sys.argv)>1 and (sys.argv[1] == '-console' or sys.argv[1] == '--console'): raise Exception('skip kivy')
    from kivy.app import App
    from kivy.uix.gridlayout import GridLayout
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.core.window import Window
    class Quest(App):
        def build(self):
            self.textLabel, self.scroll = None, None
            self.font_size = 20
            self.data = data = GridLayout(cols=1, size_hint=(1, None))
            data.bind(minimum_height=data.setter('height'))
            data.bind(size=self.resize)
            Window.bind(on_resize=self.resize)
            self.show_data()
            return data
        
        def resize(self, *args):
            obj = [x for x in self.data.children if not isinstance(x, GridLayout) and x!=self.scroll]
            if self.textLabel: obj.append(self.textLabel)
            h = Window.size[1] - 60
            for w in obj:
                w.text_size = (self.data.width-w.padding[0]*2, None)
                w.texture_update()
                w.size = (w.texture_size[0]+w.padding[0]*2, w.texture_size[1]+w.padding[1]*2)
                if w != self.textLabel: h -= w.size[1]
            if self.scroll: self.scroll.size = (self.data.width, h)
        
        def button_pressed(self, button):
            try: n = int(button.action_num)
            except Exception: pass
            if n>=0 and n<len(quest.alternatives): quest.action(n)
            try: self.title = quest.title
            except Exception: pass
            self.show_data()
        
        def resize_text(self, b):
            if b.text == '+':
                self.font_size += 2
            else:
                self.font_size = max(6, self.font_size - 2)
            self.show_data()
        
        def restart(self, b):
            global quest
            quest = QuestEngine()
            os.remove(os.path.join(base_dir, 'autosave'))
            self.show_data()
        
        def show_data(self):
            self.data.clear_widgets()
            menu = GridLayout(cols=3, size_hint=(1, None), height=60)
            button_plus = Button(text='+', size_hint=(None, None), size=(menu.height*3, menu.height))
            button_minus = Button(text='-', size_hint=(None, None), size=(menu.height*3, menu.height))
            button_restart = Button(text='Restart', size_hint=(None, None), size=(menu.height*3, menu.height))
            button_plus.bind(on_release = self.resize_text)
            button_minus.bind(on_release = self.resize_text)
            button_restart.bind(on_release = self.restart)
            menu.add_widget(button_plus)
            menu.add_widget(button_minus)
            menu.add_widget(button_restart)
            self.data.add_widget(menu)
            if quest.new_loc:
                text = quest.res + '\n\n' + quest.loc_msg
            else:
                text = quest.loc_msg + '\n\n' + quest.res
            self.scroll = ScrollView(size_hint=(1, None), do_scroll_x=False)
            self.textLabel = Label(text=text.strip(), padding=(5, 2), size_hint=(1, None), font_size=self.font_size)
            self.scroll.add_widget(self.textLabel)
            self.data.add_widget(self.scroll)
            if quest.loc != '_':
                for i in range(len(quest.alternatives)):
                    b = Button(text=quest.alternatives[i], size_hint=(1, None), padding=(5, 2), font_size=self.font_size)
                    b.action_num = i
                    b.bind(on_release=self.button_pressed)
                    self.data.add_widget(b)
            else:
                os.remove(os.path.join(base_dir, 'autosave'))
                b = Button(text='Exit', size_hint=(1, None), padding=(5, 2), font_size=self.font_size)
                b.bind(on_release=exit)
                self.data.add_widget(b)
            self.resize()

    if __name__ == "__main__": Quest().run()
    exit()
except Exception as e: print(e)
def print_wrap(res):
    for l in res.split('\\\\'):
        try:
            s = ''
            for w in l.split():
                if len(s)+len(w) >= min(80, shutil.get_terminal_size()[0]):
                    print(s)
                    s = ''
                s += w + ' '
            if len(s)>0: print(s)
        except Exception: print(l)
while quest.loc != '_':
    if quest.new_loc and quest.loc_msg != '': print_wrap(quest.loc_msg)
    print(''.join(['\n%d) %s' % (i, quest.alternatives[i]) for i in range(len(quest.alternatives))]))
    n = -1
    try:
        while n<0 or n>=len(quest.alternatives): n = int(input('\n> '))
    except Exception:
        quest.new_loc = True
        continue
    quest.action(n)
    print_wrap(quest.res)
os.remove(os.path.join(base_dir, 'autosave'))
input()

