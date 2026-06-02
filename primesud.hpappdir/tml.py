###################################
## Text Mode Layer (tml) v1.00   ##
## (c) Piotr Kowalewski (komame) ##
## August 30 - October 14, 2024  ##
###################################
from hpprime import eval as ppleval, strblit2, grobw, grobh, fillrect, rect, keyboard
from uio import FileIO
from cas import get_key

class tml:
    def __init__(self, font=None, status='', dark_mode=False, tab_size=4, ext_char_map = {}, symb_key_map = {}, bg_color = 0x3000, grob=9):
        # Load font data
        if font is None:
            afiles = ppleval('AFiles')
            try:
                font = next(fname for fname in afiles if fname.endswith('.font'))
            except StopIteration:
                raise OSError("No font file found")
            font = font.rsplit('.',1)[0]
            del afiles
        ftype = ppleval('G%d:=AFiles("%s.font")' % (grob, font))
        try:
            with FileIO('%s.font' % font,'rb') as ffile:
                ffile.seek(-1,2)
                cfg = ord(ffile.read(1))
        except OSError:
            raise OSError("File '%s.font' not found" % font)
        except Exception:
            ftype = ''  # invalid file
        if ftype == 'PNG':
            self.char_width = (cfg >> 3) + 4
        if ftype != 'PNG' or cfg & 3 != 0 or grobw(grob) % self.char_width != 0:
            raise ValueError("Invalid font file '%s.font'" % font)
        # Initialize terminal dimensions and properties
        self.char_height = grobh(grob)
        self.columns = 320 // self.char_width
        self.rows = 240 // self.char_height - (status != None) * 2
        self.cursor_x = 0
        self.cursor_y = 0
        self.width = self.columns * self.char_width
        self.height = self.rows * self.char_height
        self.back_color = bg_color
        self.grob = grob
        self.status_text = status
        self.tab_size = tab_size
        self.is_alpha = False
        self.is_shift = False
        self.alpha_lock = False
        self.shift_lock = False
        self.alpha_hold = False
        self.shift_hold = False
        self.symb_hold = False
        self.symb_index = 0
        self.last_keyboard_state = keyboard()
        self.char_map = {chr(i): i-32 for i in range(32, 127)}
        self.char_map.update(ext_char_map)
        self.key_map = tml._default_key_map()
        self.symb_key_map = symb_key_map
        
        if dark_mode:
            ppleval('INVERT_P(G%d)' % grob)
        else:
            self.back_color = 0xFFFFFF
        fillrect(0, 0, 0, 320, 240, self.back_color, self.back_color)
        if status != None:
            y = self.height + (self.char_height >> 1)
            self.print_xy(0, self.rows, ' ' * self.columns)
            rect(0, 0, y, 320, 2, 0x7F7F7F)
            self.set_status(status)
            self._refresh_indicators()

    def print(self, *args, sep=' ', end='\n'):
        # Output text based on the provided arguments
        text = sep.join(str(arg) for arg in args) + end
        for char in text:
            self._put_char(char)

    def clear(self):
        # Clear the entire screen and reset cursor position
        fillrect(0, 0, 0, self.width, self.height, self.back_color, self.back_color)
        self.cursor_x = 0
        self.cursor_y = 0

    def set_cursor(self, x, y):
        # Set the cursor position (if within bounds)
        if 0 <= x < self.columns and 0 <= y < self.rows:
            self.cursor_x = x
            self.cursor_y = y
        else:
            raise ValueError("Cursor position out of bounds")

    def input(self, prompt=None, length=0, alpha=True, shift=False, new_line=True):
        # Custom input method to gather text input from the user
        self.alpha_lock = alpha
        self.shift_lock = False
        if self.alpha_lock:
            self.is_alpha = False
            self.shift_lock = shift
        if self.shift_lock:
            self.is_shift = False
        else:
            self.is_shift = shift
        symb_entered = False
        self._refresh_indicators()
        if prompt:
            self.print(prompt, end='')
        start_x = self.cursor_x
        length = min(length, self.columns - start_x - 1) if length > 0 else self.columns - self.cursor_x - 1
        input_string = ''
        self._invert_cursor()
        
        try:
            while True:
                char = self.read_key()
                if char == None:
                    continue
                if char == '\n':  # Enter key
                    self._invert_cursor()
                    if new_line:
                        self._put_char('\n')
                    break
                elif char == '\b':
                    if self.is_shift:  # Delete
                        self._invert_cursor()
                        _x = self.cursor_x - start_x
                        input_string = input_string[:_x] + input_string[_x + 1:]
                        self.print_xy(self.cursor_x, self.cursor_y, input_string[_x:] + ' ')
                        self._invert_cursor()
                    elif self.cursor_x > start_x:  # Backspace
                        self._invert_cursor()
                        _x = self.cursor_x - start_x
                        input_string = input_string[:_x - 1] + input_string[_x:]
                        self.cursor_x -= 1
                        self.print_xy(self.cursor_x, self.cursor_y, input_string[_x - 1:] + ' ')
                        self._invert_cursor()
                elif char == '\e':  # Escape or clear line
                    self._invert_cursor()
                    self.cursor_x = start_x + len(input_string)
                    while self.cursor_x > start_x:
                        self.cursor_x -= 1
                        self._draw_char(' ')
                    self._invert_cursor()
                    input_string = ''
                elif char == '\L':  # Left
                    if self.cursor_x > start_x:
                        self._invert_cursor()
                        if self.is_shift:
                            self.cursor_x = start_x
                        else:
                            self.cursor_x -= 1
                        self._invert_cursor()
                elif char == '\R':  # Right
                    end_x = start_x + len(input_string)
                    if self.cursor_x < end_x:
                        self._invert_cursor()
                        if self.is_shift:
                            self.cursor_x = end_x
                        else:
                            self.cursor_x += 1
                        self._invert_cursor()
                elif char == '\SR':  # Symb released
                    if symb_entered:
                        self._invert_cursor()
                        self.cursor_x += 1
                        self._invert_cursor()
                        symb_entered = False
                else:
                    _x = self.cursor_x - start_x
                    if self.symb_hold:
                        if symb_entered:
                            input_string = input_string[:_x] + char + input_string[_x+1:]
                        else:
                            if len(input_string + char) - 1 < length:
                                input_string = input_string[:_x] + char + input_string[_x:]
                                symb_entered = True
                        self._invert_cursor()
                        self.print_xy(self.cursor_x, self.cursor_y, input_string[_x:])
                        self._invert_cursor()
                    elif len(input_string + char) - 1 < length:
                        self._invert_cursor()
                        input_string = input_string[:_x] + char + input_string[_x:]
                        self.print_xy(self.cursor_x, self.cursor_y, input_string[_x:])
                        self.cursor_x += 1
                        self._invert_cursor()
                if self.is_shift and not self.symb_hold:
                    self.is_shift = False
                    self._refresh_indicators()
                
        except KeyboardInterrupt:
            # Handle keyboard interrupt
            self._invert_cursor()
            if new_line:
                self._put_char('\n')
            input_string = ''

        self.alpha_lock = self.is_alpha = self.shift_lock = self.is_shift = False        
        self._refresh_indicators()
        return input_string

    def read_key(self, code=False):
        # Read key input from the keyboard
        while True:
            current_state = keyboard()
            changed_keys = current_state ^ self.last_keyboard_state  # XOR to find changes
            if changed_keys:  # Check if there are any changes
                self.last_keyboard_state = current_state  # Update the last known state
                for key_index in range(52):  # 52 possible keys
                    if changed_keys & (1 << key_index):  # Check if the i-th key state has changed
                        if current_state & (1 << key_index):  # Check if the i-th key is pressed
                            get_key()
                            if code:
                                return key_index
                            if key_index == 36:  # alpha key
                                self.alpha_hold = True
                                if self.alpha_lock:
                                    if self.is_shift:
                                        self.shift_lock = not self.shift_lock
                                    else:
                                        self.alpha_lock = self.is_alpha = False
                                        self.shift_lock = False
                                    self.is_shift = False
                                elif self.is_alpha:
                                    if self.is_shift:
                                        if self.alpha_lock:
                                            self.shift_lock = not self.shift_lock
                                        else:    
                                            self.alpha_lock = True
                                        self.is_shift = False
                                    else:
                                        self.alpha_lock = True
                                else:
                                    self.is_alpha = True
                                self._refresh_indicators()
                            elif key_index == 41:  # Shift key
                                self.shift_hold = True
                                if self.is_shift:
                                    self.is_shift = self.shift_lock if not self.is_shift else False
                                else:
                                    self.is_shift = True
                                self._refresh_indicators()
                            elif key_index == 1:  # Symb key
                                self.symb_hold = True
                                self.symb_index = 0
                            else:
                                if self.shift_hold:
                                    self.is_shift = True
                                if self.alpha_hold:
                                    self.is_alpha = True
                                modifiers_state = ((self.is_shift ^ self.shift_lock) << 1) | (self.is_alpha | self.alpha_lock)

                                if self.symb_hold:
                                    symbols = self.symb_key_map.get(key_index, [None,None,None,None])[modifiers_state]
                                    if symbols != None:
                                        symb = symbols[self.symb_index % len(symbols)]
                                        self.symb_index = (self.symb_index + 1) % len(symbols)
                                        return symb
                                else:
                                    if not self.alpha_lock:
                                        self.is_alpha = False
                                        self._refresh_indicators()
                                    return self.key_map.get(key_index, [None,None,None,None])[modifiers_state]
                        else:  # key released
                            if key_index == 36:  # alpha key
                                self.alpha_hold = False
                            elif key_index == 41:  # Shift key
                                self.shift_hold = False
                            elif key_index == 1:  # Symb key
                                self.symb_hold = False
                                if code == False:
                                    return '\SR'
                            self._refresh_indicators()
            ppleval('WAIT(1/1e3)')

    def get_keys(self):
        # Return the list of currently pressed keys (codes)
        keys = []
        key_index = 0
        current_state = keyboard()
        while current_state != 0:
          if current_state & 1:
            keys.append(key_index)
          current_state >>= 1
          key_index += 1
        return keys

    def set_status(self, text):
        # Set the status text and ensure it fits within the display width
        length = self.columns-6
        self.status_text = "%-*s" % (length, text[:length])
        self.print_xy(0, self.rows + 1, self.status_text)

    def print_xy(self, x, y, text):
        # Print text at specified position (x, y) on the screen
        for i in text:
            self._draw_char_xy(i, x, y)
            x += 1

    @staticmethod
    def _default_key_map():
        # Map key index to respective character
        return {
            # [no modifiers, Alpha, Shift, Alpha+Shift]
            4: ['\e','\e','\e','\e'],
            7: ['\L','\L','\L','\L'],
            8: ['\R','\R','\R','\R'],
            14: [None,'a',None,'A'],
            15: [None,'b',None,'B'],
            16: [None,'c',None,'C'],
            17: [None,'d',None,'D'],
            18: [None,'e',None,'E'],
            19: ['\b','\b','\b','\b'],
            20: ['^','f',None,'F'],
            21: [None,'g',None,'G'],
            22: [None,'h',None,'H'],
            23: [None,'i',None,'I'],
            24: [None,'j',None,'J'],
            25: [None,'k',None,'K'],
            26: [None,'l',None,'L'],
            27: [None,'m','|','M'],
            28: ['()','n',"'",'N'],
            29: [',','o',None,'O'],
            30: ['\n','\n','\n','\n'],
            31: [None,'p',None,'P'],
            32: ['7','q','&','Q'],
            33: ['8','r','{}','R'],
            34: ['9','s','!','S'],
            35: ['/','t','%','T'],
            37: ['4','u','$','U'],
            38: ['5','v','[]','V'],
            39: ['6','w','^','W'],
            40: ['*','x','','X'],
            42: ['1','y','~','Y'],
            43: ['2','z','@','Z'],
            44: ['3','#','?','#'],
            45: ['-',':',None,':'],
            47: ['0','"','`','"'],
            48: ['.','.','=','.'],
            49: [' ',' ','_','_'],
            50: ['+',';','\\','|']
            }
                                        
    def _refresh_indicators(self):
        # Refresh the indicators on the screen showing shift, alpha, and lock states
        pos = self.columns-6
        indic = ''
        if self.is_shift or self.shift_hold:
            indic += '^'
        if self.shift_lock:
            indic += 'SL'
        if self.alpha_lock:
            if self.shift_lock:
                indic += '+'
            indic += 'AL' if (self.is_shift | self.shift_hold) ^ self.shift_lock else 'al'
        elif self.is_alpha or self.alpha_hold:
            indic += 'A' if (self.is_shift | self.shift_hold) ^ self.shift_lock else 'a'
        x = self.columns-6
        y = self.rows
        indic = "%6s" % indic
        self.print_xy(x, y + 1, indic)

    def _put_char(self, char):
        # Place character on the screen and manage cursor position
        if char == '\n':
            self.cursor_x = 0
            self.cursor_y += 1
            self._end_of_screen_check()
        elif char == '\t':
            # Handle tabulation based on tab size
            spaces_to_next_tab = self.tab_size - (self.cursor_x % self.tab_size)
            self.cursor_x += spaces_to_next_tab
            if self.cursor_x >= self.columns:
                self.cursor_x = 0
                self.cursor_y += 1
                self._end_of_screen_check()
        else:
            self._draw_char(char)
            self.cursor_x += 1
            if self.cursor_x >= self.columns:
                self.cursor_x = 0
                self.cursor_y += 1
                self._end_of_screen_check()

    def _draw_char(self, char):
        # Draw character to the screen using a bitmap
        # char_code = ord(char)
        if char in self.char_map:
            index = self.char_map[char]
            char_x = index * self.char_width
            strblit2(0, self.cursor_x * self.char_width, self.cursor_y * self.char_height, self.char_width, self.char_height, self.grob, char_x, 0, self.char_width, self.char_height)

    def _draw_char_xy(self, char, x, y):
        # Draw character to the screen at (x, y) using a bitmap
        # char_code = ord(char)
        if char in self.char_map:
            index = self.char_map[char]
            char_x = index * self.char_width
            strblit2(0, x * self.char_width, y * self.char_height, self.char_width, self.char_height, self.grob, char_x, 0, self.char_width, self.char_height)

    def _end_of_screen_check(self):
        # Check if the cursor has moved past the bottom edge of the screen
        if self.cursor_y >= self.rows:
            self._scroll_up()
    
    def _scroll_up(self):
        # Scroll the screen up by one line
        strblit2(0, 0, 0, self.width, self.height - self.char_height, 0, 0, self.char_height, self.width, self.height - self.char_height)
        fillrect(0, 0, self.height - self.char_height, self.width, self.char_height, self.back_color, self.back_color)
        self.cursor_y -= 1

    def _invert_cursor(self):
        # Invert the cursor display
        ppleval('INVERT_P(%d,%d,%d,%d)' % (self.cursor_x * self.char_width, self.cursor_y * self.char_height, self.cursor_x * self.char_width + self.char_width - 1, self.cursor_y * self.char_height + self.char_height - 1))
