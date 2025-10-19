#!/usr/bin/env python3
"""
calculator2025.py
Modern Windows-style Calculator (2025) — single-file app using PyQt6.

Features (must-have included):
 - Basic arithmetic: + - * /, parentheses, decimal
 - Percent (%) behavior
 - Backspace, Clear (C), All Clear (AC)
 - Memory: M+, M-, MR, MC
 - History (click to reuse)
 - Scientific: sin, cos, tan, ln, log, sqrt, x^y, x^2, 1/x, factorial
 - ± toggle, ANS (last answer)
 - Keyboard support (numbers, operators, Enter, Backspace, Esc)
 - Resizable, adaptive layout
 - Light/Dark theme + theme toggle
 - Mini mode (compact overlay)
 - Safe expression evaluation (AST-based) — no eval()
 - Packable to .exe with PyInstaller

Dependencies:
    pip install PyQt6

To run:
    python calculator2025.py

To make .exe:
    pip install pyinstaller
    pyinstaller --onefile --windowed --name calculator2025 calculator2025.py
"""

import sys, math, ast, traceback
from PyQt6 import QtWidgets, QtCore, QtGui

# ----------------------------
# Safe evaluator (AST-based)
# ----------------------------
SAFE_MATH = {k: getattr(math, k) for k in dir(math) if not k.startswith("__")}
SAFE_MATH.update({
    "pi": math.pi,
    "e": math.e,
    "sqrt": math.sqrt,
    "ln": math.log,
    "log": math.log10,
    "pow": pow,
    "abs": abs,
    "factorial": math.factorial,
})

class EvalError(Exception):
    pass

def safe_eval(expr: str):
    """
    Safely evaluate math expression using ast.
    Supports numbers, + - * / ** % unary ops, parentheses, and allowed functions/names.
    """
    # Quick cleanup
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**").replace("√", "sqrt")
    # Parse
    try:
        node = ast.parse(expr, mode='eval')
    except Exception:
        raise EvalError("Syntax error")
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            else:
                raise EvalError("Invalid constant")
        if isinstance(node, ast.BinOp):
            l = _eval(node.left); r = _eval(node.right)
            op = node.op
            if isinstance(op, ast.Add): return l + r
            if isinstance(op, ast.Sub): return l - r
            if isinstance(op, ast.Mult): return l * r
            if isinstance(op, ast.Div):
                if r == 0: raise EvalError("Division by zero")
                return l / r
            if isinstance(op, ast.Mod): return l % r
            if isinstance(op, ast.Pow): return l ** r
            raise EvalError("Unsupported binary op")
        if isinstance(node, ast.UnaryOp):
            val = _eval(node.operand)
            if isinstance(node.op, ast.USub): return -val
            if isinstance(node.op, ast.UAdd): return +val
            raise EvalError("Unsupported unary op")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise EvalError("Invalid function")
            fname = node.func.id
            if fname not in SAFE_MATH:
                raise EvalError(f"Function {fname} not allowed")
            args = [_eval(a) for a in node.args]
            try:
                return SAFE_MATH[fname](*args)
            except Exception as e:
                raise EvalError("Function error")
        if isinstance(node, ast.Name):
            if node.id in SAFE_MATH:
                return SAFE_MATH[node.id]
            raise EvalError("Name not allowed")
        raise EvalError("Unsupported expression")
    result = _eval(node)
    if isinstance(result, complex):
        raise EvalError("Complex result not supported")
    return result

# ----------------------------
# UI Components
# ----------------------------
class RoundedButton(QtWidgets.QPushButton):
    def __init__(self, text, slot=None, min_h=48):
        super().__init__(text)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(min_h)
        f = QtGui.QFont("Segoe UI", 11)
        self.setFont(f)
        if slot:
            self.clicked.connect(slot)

class CalcWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calculator 2025")
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowType.Window)
        self.setWindowIcon(QtGui.QIcon())  # add icon path if desired
        self.setMinimumSize(360, 560)
        self.memory = 0.0
        self.history = []  # list of (expr, value)
        self.last_ans = 0.0
        self.mini_mode = False
        self.dark_mode = True

        self._build_ui()
        self._apply_styles()
        self._connect_shortcuts()

    def _build_ui(self):
        # Main layout
        main = QtWidgets.QHBoxLayout(self)
        main.setContentsMargins(12,12,12,12)

        # Left: calculator area
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(8)

        # Top bar: title, theme toggle, mini toggle, close
        topbar = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Calculator")
        title.setFont(QtGui.QFont("Segoe UI", 14, QtGui.QFont.Weight.DemiBold))
        topbar.addWidget(title)
        topbar.addStretch()

        self.theme_btn = QtWidgets.QPushButton("🌗")
        self.theme_btn.setToolTip("Toggle theme")
        self.theme_btn.setFixedSize(36,28)
        self.theme_btn.clicked.connect(self.toggle_theme)
        topbar.addWidget(self.theme_btn)

        self.mini_btn = QtWidgets.QPushButton("☐")
        self.mini_btn.setToolTip("Toggle mini mode")
        self.mini_btn.setFixedSize(36,28)
        self.mini_btn.clicked.connect(self.toggle_mini_mode)
        topbar.addWidget(self.mini_btn)

        left.addLayout(topbar)

        # Expression label (small) + result lineedit
        self.expr_label = QtWidgets.QLabel("")
        self.expr_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.expr_label.setFont(QtGui.QFont("Segoe UI", 10))
        left.addWidget(self.expr_label)

        self.result_edit = QtWidgets.QLineEdit("0")
        self.result_edit.setReadOnly(True)
        self.result_edit.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.result_edit.setFont(QtGui.QFont("Segoe UI", 28, QtGui.QFont.Weight.Bold))
        self.result_edit.setMinimumHeight(72)
        self.result_edit.setFrame(False)
        left.addWidget(self.result_edit)

        # Memory row
        mem_row = QtWidgets.QHBoxLayout()
        for label, slot in [("MC", self.mem_clear), ("MR", self.mem_recall), ("M+", self.mem_add), ("M-", self.mem_sub)]:
            b = RoundedButton(label, slot, min_h=36)
            b.setMaximumWidth(80)
            mem_row.addWidget(b)
        left.addLayout(mem_row)

        # Buttons grid (use QGridLayout)
        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(8)

        # We'll prepare a structure of buttons (r, c, text, slot, colspan)
        btns = [
            (0,0,"(", lambda: self._add("(")), (0,1,")", lambda: self._add(")")), (0,2,"⌫", self.backspace), (0,3,"AC", self.all_clear),
            (1,0,"7", lambda: self._add("7")), (1,1,"8", lambda: self._add("8")), (1,2,"9", lambda: self._add("9")), (1,3,"÷", lambda: self._add("/")),
            (2,0,"4", lambda: self._add("4")), (2,1,"5", lambda: self._add("5")), (2,2,"6", lambda: self._add("6")), (2,3,"×", lambda: self._add("*")),
            (3,0,"1", lambda: self._add("1")), (3,1,"2", lambda: self._add("2")), (3,2,"3", lambda: self._add("3")), (3,3,"-", lambda: self._add("-")),
            (4,0,"0", lambda: self._add("0")), (4,1,".", lambda: self._add(".")), (4,2,"%", self.on_percent), (4,3,"+", lambda: self._add("+")),
            # scientific / extra row (initially visible)
            (5,0,"sin", lambda: self._add("sin(")), (5,1,"cos", lambda: self._add("cos(")), (5,2,"tan", lambda: self._add("tan(")), (5,3,"^", lambda: self._add("**")),
            (6,0,"ln", lambda: self._add("ln(")), (6,1,"log", lambda: self._add("log(")), (6,2,"√", lambda: self._add("sqrt(")), (6,3,"!", self.on_factorial),
            (7,0,"±", self.toggle_plusminus), (7,1,"ANS", self.insert_ans), (7,2,"1/x", self.on_reciprocal), (7,3,"=", self.on_equals),
        ]

        # Add buttons to grid
        for r,c,t,slot in btns:
            btn = RoundedButton(t, slot)
            # larger 0 button spans 2 columns? keep simple: 0 single cell for consistency in resizing
            self.grid.addWidget(btn, r, c)
        left.addLayout(self.grid)

        # keyboard input helper (hidden QLineEdit for pasting/typing) - allow focus
        self.hidden_input = QtWidgets.QLineEdit()
        self.hidden_input.setVisible(False)
        left.addWidget(self.hidden_input)

        main.addLayout(left, 3)

        # Right: history panel
        self.history_panel = QtWidgets.QVBoxLayout()
        hlabel = QtWidgets.QLabel("History")
        hlabel.setFont(QtGui.QFont("Segoe UI", 12, QtGui.QFont.Weight.DemiBold))
        self.history_panel.addWidget(hlabel)
        self.history_list = QtWidgets.QListWidget()
        self.history_list.itemClicked.connect(self.on_history_click)
        self.history_panel.addWidget(self.history_list)
        main.addLayout(self.history_panel, 1)

        # set shortcuts for buttons
        self._assign_button_shortcuts()

        # initial state
        self._update_display()

    # ----------------------------
    # UI behaviors
    # ----------------------------
    def _assign_button_shortcuts(self):
        # Map keys to actions
        key_map = {
            QtCore.Qt.Key.Key_0: lambda: self._add("0"),
            QtCore.Qt.Key.Key_1: lambda: self._add("1"),
            QtCore.Qt.Key.Key_2: lambda: self._add("2"),
            QtCore.Qt.Key.Key_3: lambda: self._add("3"),
            QtCore.Qt.Key.Key_4: lambda: self._add("4"),
            QtCore.Qt.Key.Key_5: lambda: self._add("5"),
            QtCore.Qt.Key.Key_6: lambda: self._add("6"),
            QtCore.Qt.Key.Key_7: lambda: self._add("7"),
            QtCore.Qt.Key.Key_8: lambda: self._add("8"),
            QtCore.Qt.Key.Key_9: lambda: self._add("9"),
            QtCore.Qt.Key.Key_Plus: lambda: self._add("+"),
            QtCore.Qt.Key.Key_Minus: lambda: self._add("-"),
            QtCore.Qt.Key.Key_Asterisk: lambda: self._add("*"),
            QtCore.Qt.Key.Key_Slash: lambda: self._add("/"),
            QtCore.Qt.Key.Key_Period: lambda: self._add("."),
            QtCore.Qt.Key.Key_ParenLeft: lambda: self._add("("),
            QtCore.Qt.Key.Key_ParenRight: lambda: self._add(")"),
            QtCore.Qt.Key.Key_Enter: self.on_equals,
            QtCore.Qt.Key.Key_Return: self.on_equals,
            QtCore.Qt.Key.Key_Backspace: self.backspace,
            QtCore.Qt.Key.Key_Escape: self.all_clear,
        }
        # store for keyPressEvent
        self._key_map = key_map

    def _connect_shortcuts(self):
        # Additional shortcuts: copy result (Ctrl+C), paste (Ctrl+V)
        copy_sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+C"), self)
        copy_sc.activated.connect(self.copy_result)
        paste_sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+V"), self)
        paste_sc.activated.connect(self.paste_into_expr)

    def _apply_styles(self):
        # basic modern style with light and dark variants
        self.setStyleSheet(self._stylesheet())

    def _stylesheet(self):
        if self.dark_mode:
            bg = "#0F1724"  # deep navy
            card = "rgba(255,255,255,0.04)"
            text = "#E6EEF3"
            sub = "#9FB4C8"
            accent = "#6EE7B7"  # gentle mint
            btn = "rgba(255,255,255,0.04)"
            hover = "rgba(255,255,255,0.06)"
        else:
            bg = "#F6F7FB"
            card = "rgba(0,0,0,0.04)"
            text = "#0F1724"
            sub = "#4B5563"
            accent = "#2563EB"  # blue
            btn = "rgba(0,0,0,0.04)"
            hover = "rgba(0,0,0,0.06)"
        return f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {bg}, stop:1 {bg});
                color: {text};
                font-family: "Segoe UI", "Inter", sans-serif;
            }}
            QLineEdit {{ background: transparent; color: {text}; }}
            QLabel {{ color: {sub}; }}
            QListWidget {{
                background: {card};
                border-radius: 10px;
                padding: 6px;
            }}
            QPushButton {{
                background: {btn};
                color: {text};
                border: none;
                border-radius: 10px;
                padding: 8px;
            }}
            QPushButton:hover {{ background: {hover}; }}
            QPushButton:pressed {{ background: rgba(0,0,0,0.12); transform: translate(0px,1px); }}
            QLineEdit[readOnly="true"] {{ font-weight: 600; }}
        """

    # ----------------------------
    # Input / Expression handling
    # ----------------------------
    def _add(self, token: str):
        cur = self.expr_label.text()
        cur += token
        self.expr_label.setText(cur)
        # realtime evaluate
        try:
            val = safe_eval(cur)
            self._set_result_display(val)
        except Exception:
            # don't change result until valid
            pass

    def backspace(self):
        txt = self.expr_label.text()
        if txt:
            self.expr_label.setText(txt[:-1])
            try:
                val = safe_eval(self.expr_label.text()) if self.expr_label.text() else 0
                self._set_result_display(val)
            except Exception:
                pass

    def on_percent(self):
        # percent converts last number into division by 100; simple implementation: append '/100'
        self._add("/100")

    def on_factorial(self):
        expr = self.expr_label.text().strip()
        if not expr:
            return
        # try evaluate expr and apply factorial if integer and non-negative
        try:
            val = safe_eval(expr)
            if val < 0 or int(val) != val:
                raise EvalError("Factorial domain")
            res = math.factorial(int(val))
            self._commit_result(res, f"fact({int(val)})")
        except Exception:
            # fallback: append 'factorial(' to expression for user to complete
            self._add("factorial(")

    def toggle_plusminus(self):
        txt = self.expr_label.text().strip()
        if not txt:
            self._add("-")
            return
        try:
            val = safe_eval(txt)
            val = -val
            # replace display
            self.expr_label.setText(str(val))
            self._set_result_display(val)
        except Exception:
            # naive toggle: add/remove leading -
            if txt.startswith("-"):
                self.expr_label.setText(txt[1:])
            else:
                self.expr_label.setText("-" + txt)

    def insert_ans(self):
        self._add(str(self.last_ans))

    def on_reciprocal(self):
        txt = self.expr_label.text().strip()
        if not txt:
            return
        try:
            val = safe_eval(txt)
            if val == 0:
                raise EvalError("Division by zero")
            res = 1.0 / val
            self._commit_result(res, f"1/({txt})")
        except Exception:
            # append reciprocal marker
            self._add("1/(")

    def on_equals(self):
        expr = self.expr_label.text().strip()
        if not expr:
            return
        try:
            val = safe_eval(expr)
            self._commit_result(val, expr)
            self._set_result_display(val)
            self.expr_label.setText("")  # reset expr to empty; result visible
        except EvalError:
            self._set_result_text("Error")
        except Exception:
            self._set_result_text("Error")

    def _set_result_display(self, val):
        # format nicely
        if isinstance(val, float):
            out = f"{val:.12g}"
        else:
            out = str(val)
        self.result_edit.setText(out)

    def _set_result_text(self, text):
        self.result_edit.setText(text)

    def _commit_result(self, value, expr):
        # store history and last ans
        self.last_ans = value
        self.history.append((expr, value))
        disp = f"{value:.12g}" if isinstance(value, float) else str(value)
        self.history_list.addItem(f"{expr} = {disp}")
        self.history_list.scrollToBottom()

    def all_clear(self):
        self.expr_label.setText("")
        self.result_edit.setText("0")

    # ----------------------------
    # Memory operations
    # ----------------------------
    def mem_clear(self):
        self.memory = 0.0

    def mem_recall(self):
        self._add(str(self.memory))

    def mem_add(self):
        # add current visible result if numeric
        try:
            v = float(self.result_edit.text())
            self.memory += v
        except Exception:
            try:
                v = float(safe_eval(self.expr_label.text()))
                self.memory += v
            except Exception:
                return

    def mem_sub(self):
        try:
            v = float(self.result_edit.text())
            self.memory -= v
        except Exception:
            try:
                v = float(safe_eval(self.expr_label.text()))
                self.memory -= v
            except Exception:
                return

    # ----------------------------
    # History
    # ----------------------------
    def on_history_click(self, item):
        text = item.text()
        if "=" in text:
            expr = text.split("=",1)[0].strip()
            self.expr_label.setText(expr)

    # ----------------------------
    # Theme & Mini Mode
    # ----------------------------
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self._apply_styles()

    def toggle_mini_mode(self):
        # mini mode hides history and scientific rows to be compact
        self.mini_mode = not self.mini_mode
        # show/hide history
        if self.mini_mode:
            # hide history widget and scientific rows: hide rows 5,6,7
            for r in [5,6,7]:
                for c in range(4):
                    w = self.grid.itemAtPosition(r,c)
                    if w:
                        w.widget().setVisible(False)
            self.history_list.setVisible(False)
            self.setMinimumSize(320, 420)
        else:
            for r in [5,6,7]:
                for c in range(4):
                    w = self.grid.itemAtPosition(r,c)
                    if w:
                        w.widget().setVisible(True)
            self.history_list.setVisible(True)
            self.setMinimumSize(360, 560)

    # ----------------------------
    # Clipboard helpers
    # ----------------------------
    def copy_result(self):
        cb = QtWidgets.QApplication.clipboard()
        cb.setText(self.result_edit.text())

    def paste_into_expr(self):
        cb = QtWidgets.QApplication.clipboard()
        txt = cb.text()
        if txt:
            # sanitize: only allow digits, operators, parens, dot, letters (for functions)
            allowed = "0123456789.+-*/()%eEpiPIabcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
            filtered = "".join(ch for ch in txt if ch in allowed)
            self._add(filtered)

    # ----------------------------
    # Keyboard handling
    # ----------------------------
    def keyPressEvent(self, event):
        k = event.key()
        if k in self._key_map:
            try:
                self._key_map[k]()
            except Exception:
                pass
            return
        # handle direct char input
        ch = event.text()
        if ch and ch in "0123456789.+-*/()%^":
            # map ^ to **
            if ch == "^":
                self._add("**")
            elif ch == "%":
                self.on_percent()
            else:
                self._add(ch)
            return
        # Enter / Return handled in key map
        super().keyPressEvent(event)

    # ----------------------------
    # Utility
    # ----------------------------
    def _update_display(self):
        # update theme etc.
        self._apply_styles()

# ----------------------------
# Run app
# ----------------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    # High DPI
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    window = CalcWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
