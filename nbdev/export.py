# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/01_export.ipynb.

#nbdev_cell auto 0
__all__ = ['extract_comments', 'NotebookProcessor', 'find_var', 'read_var', 'update_var', 'ModuleMaker', 'retr_exports', 'relative_import', 'absolute_import', 'update_import', 'ExportModuleProcessor']


#nbdev_cell ../nbs/01_export.ipynb 2
#export
from .read import *

from .imports import *
from fastcore.script import *
from fastcore.imports import *

from collections import defaultdict
from pprint import pformat
import ast,contextlib


#nbdev_cell ../nbs/01_export.ipynb 7
#export
def extract_comments(ss):
    "Take leading comments from lines of code in `ss`, remove `#`, and split"
    ss = ss.splitlines()
    first_code = first(i for i,o in enumerate(ss) if re.match('\s*[^#\s]', o))
    return L((s.strip()[1:]).strip().split() for s in ss[:first_code]).filter()


#nbdev_cell ../nbs/01_export.ipynb 10
#export
class NotebookProcessor:
    "Base class for nbdev notebook processors"
    def __init__(self, path, debug=False): self.nb,self.path,self.debug = read_nb(path),Path(path),debug


#nbdev_cell ../nbs/01_export.ipynb 16
#export
@patch
def process_comment(self:NotebookProcessor, comment, cell):
    cmd,*args = comment
    cmd = f"{cmd}_{cell.cell_type}"
    if self.debug: print(cmd, args)
    if not hasattr(self, cmd): return
    try: getattr(self,cmd)(comment,cell, *args)
    except TypeError: pass


#nbdev_cell ../nbs/01_export.ipynb 19
#export
@patch
def process_cell(self:NotebookProcessor, cell):
    comments = extract_comments(cell.source)
    if not comments: return self.no_cmd(cell)
    for comment in comments: self.process_comment(comment, cell)
    return cell

@patch
def no_cmd(self:NotebookProcessor, cell): return cell


#nbdev_cell ../nbs/01_export.ipynb 22
#export
@patch
def process(self:NotebookProcessor):
    "Process all cells with `process_cell` and replace `self.nb.cells` with result"
    for i in range_of(self.nb.cells): self.nb.cells[i] = self.process_cell(self.nb.cells[i])


#nbdev_cell ../nbs/01_export.ipynb 28
#export
def find_var(lines, varname):
    "Find the line numbers where `varname` is defined in `lines`"
    start = first(i for i,o in enumerate(lines) if o.startswith(varname))
    if start is None: return None,None
    empty = ' ','\t'
    if start==len(lines)-1 or lines[start+1][:1] not in empty: return start,start+1
    end = first(i for i,o in enumerate(lines[start+1:]) if o[:1] not in empty)
    return start,len(lines) if end is None else (end+start+1)


#nbdev_cell ../nbs/01_export.ipynb 30
#export
def read_var(code, varname):
    "Eval and return the value of `varname` defined in `code`"
    lines = code.splitlines()
    start,end = find_var(lines, varname)
    if start is None: return None
    res = [lines[start].split('=')[-1].strip()]
    res += lines[start+1:end]
    try: return eval('\n'.join(res))
    except SyntaxError: raise Exception('\n'.join(res)) from None


#nbdev_cell ../nbs/01_export.ipynb 32
#export
def update_var(varname, func, fn=None, code=None):
    "Update the definition of `varname` in file `fn`, by calling `func` with the current definition"
    if fn:
        fn = Path(fn)
        code = fn.read_text()
    lines = code.splitlines()
    v = read_var(code, varname)
    res = func(v)
    start,end = find_var(lines, varname)
    del(lines[start:end])
    lines.insert(start, f"{varname} = {res}")
    code = '\n'.join(lines)
    if fn: fn.write_text(code)
    else: return code


#nbdev_cell ../nbs/01_export.ipynb 35
#export
class ModuleMaker:
    "Helper class to create exported library from notebook source cells"
    def __init__(self, dest, name, nb_path, is_new=True):
        dest,nb_path = Path(dest),Path(nb_path)
        store_attr()
        self.fname = dest/(name.replace('.','/') + ".py")
        if is_new: dest.mkdir(parents=True, exist_ok=True)
        else: assert self.fname.exists(), f"{self.fname} does not exist"
        self.dest2nb = os.path.relpath(nb_path.absolute(), dest.absolute())
        self.hdr = cell_header(self.dest2nb, Config().path('lib_path'))


#nbdev_cell ../nbs/01_export.ipynb 38
#export
_def_types = ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef
_assign_types = ast.AnnAssign, ast.Assign, ast.AugAssign

def _val_or_id(it): return [getattr(o, 'value', getattr(o, 'id', None)) for o in it.value.elts]
def _all_targets(a): return L(getattr(a,'elts',a))
def _wants(o): return isinstance(o,_def_types) and not any(L(o.decorator_list).filter(Self.id.startswith('patch')))


#nbdev_cell ../nbs/01_export.ipynb 39
#export
def retr_exports(trees):
    # include anything mentioned in "_all_", even if otherwise private
    # NB: "_all_" can include strings (names), or symbols, so we look for "id" or "value"
    assigns = trees.filter(risinstance(_assign_types))
    all_assigns = assigns.filter(lambda o: getattr(o.targets[0],'id',None)=='_all_')
    all_vals = all_assigns.map(_val_or_id).concat()
    syms = trees.filter(_wants).attrgot('name')

    # assignment targets (NB: can be multiple, e.g. "a=b=c", and/or destructuring e.g "a,b=(1,2)")
    assign_targs = L(L(assn.targets).map(_all_targets).concat() for assn in assigns).concat()
    exports = (assign_targs.attrgot('id')+syms).filter(lambda o: o and o[0]!='_')
    return (exports+all_vals).unique()


#nbdev_cell ../nbs/01_export.ipynb 40
#export
@patch
def make_all(self:ModuleMaker, cells):
    "Create `__all__` with all exports in `cells`"
    if cells is None: return ''
    parsed = cells.attrgot('parsed').concat()
    return retr_exports(parsed)


#nbdev_cell ../nbs/01_export.ipynb 43
#export
def relative_import(name, fname, level=0):
    "Convert a module `name` to a name relative to `fname`"
    assert not level
    sname = name.replace('.','/')
    if not(os.path.commonpath([sname,fname])): return name
    rel = os.path.relpath(sname, fname)
    if rel==".": return "."
    res = rel.replace(f"..{os.path.sep}", ".")
    return "." + res.replace(os.path.sep, ".")


#nbdev_cell ../nbs/01_export.ipynb 45
#export
def absolute_import(name, fname, level):
    "Unwarps a relative import in `name` according to `mod_name`"
    if not level: return name
    mods = fname.split(os.path.sep)
    if not name: return '.'.join(mods)
    return '.'.join(mods[:len(mods)-level+1]) + f".{name}"


#nbdev_cell ../nbs/01_export.ipynb 47
#export
def update_import(source, tree, libname, f):
    imps = L(tree).filter(risinstance(ast.ImportFrom))
    if not imps: return
    src = source.splitlines(True)
    for imp in imps:
        nmod = f(imp.module, libname, imp.level)
        lin = imp.lineno-1
        sec = src[lin][imp.col_offset:imp.end_col_offset]
        newsec = re.sub(f"(from +){'.'*imp.level}{imp.module}", fr"\1{nmod}", sec)
        src[lin] = src[lin].replace(sec,newsec)
    return src

@patch
def import2relative(cell:NbCell, libname):
    if not getattr(cell,'parsed',None): return
    src = update_import(cell.source, cell.parsed, libname, relative_import)
    if src: cell.set_source(src)


#nbdev_cell ../nbs/01_export.ipynb 49
#export
@patch
def make(self:ModuleMaker, cells, all_cells=None):
    "Write module containing `cells` with `__all__` generated from `all_cells`"
    for cell in all_cells: cell.import2relative(Config().lib_name)
    if not self.is_new: return self._make_exists(cells, all_cells)
    self.fname.parent.mkdir(exist_ok=True, parents=True)
    _all = self.make_all(all_cells)
    trees = cells.attrgot('parsed')
    try: last_future = max(i for i,tree in enumerate(trees) if any(
         isinstance(t,ast.ImportFrom) and t.module=='__future__' for t in tree))+1
    except ValueError: last_future=0
    with self.fname.open('w') as f:
        f.write(f"# AUTOGENERATED! DO NOT EDIT! File to edit: {self.dest2nb}.\n\n")
        export_cells(cells[:last_future], self.hdr, f, 0)
        f.write(create_all_cell(_all))
        export_cells(cells[last_future:], self.hdr, f, 1)


#nbdev_cell ../nbs/01_export.ipynb 53
#export
@patch
def _update_all(self:ModuleMaker, all_cells, alls):
    return pformat(alls + self.make_all(all_cells), width=160)

@patch
def _make_exists(self:ModuleMaker, cells, all_cells=None):
    "`make` for `is_new=False`"
    if all_cells: update_var('__all__', partial(self._update_all, all_cells), fn=self.fname)
    with self.fname.open('a') as f:
        export_cells(cells, self.hdr, f)


#nbdev_cell ../nbs/01_export.ipynb 58
#export
class ExportModuleProcessor(NotebookProcessor):
    "A `NotebookProcessor` which exports code to a module"
    def __init__(self, path, dest, mod_maker=ModuleMaker, debug=False):
        dest = Path(dest)
        store_attr()
        super().__init__(path,debug=debug)

    def process(self):
        self.modules,self.in_all = defaultdict(L),defaultdict(L)
        super().process()


#nbdev_cell ../nbs/01_export.ipynb 61
#export
@patch
def default_exp_code(self:ExportModuleProcessor, comment, cell, exp_to): self.default_exp = exp_to


#nbdev_cell ../nbs/01_export.ipynb 64
#export
@patch
def exporti_code(self:ExportModuleProcessor, comment, cell, exp_to=None):
    mod = ifnone(exp_to, '#')
    self.modules[mod].append(cell)
    return mod


#nbdev_cell ../nbs/01_export.ipynb 67
#export
@patch
def export_code(self:ExportModuleProcessor, comment, cell, exp_to=None):
    mod = self.exporti_code(comment, cell, exp_to=exp_to)
    self.in_all[mod].append(cell)
ExportModuleProcessor.exports_code = ExportModuleProcessor.export_code


#nbdev_cell ../nbs/01_export.ipynb 69
#export
@patch
def create_modules(self:ExportModuleProcessor):
    self.process()
    for mod,cells in self.modules.items():
        all_cells = self.in_all[mod]
        name = self.default_exp if mod=='#' else mod
        mm = self.mod_maker(dest=self.dest, name=name, nb_path=self.path, is_new=mod=='#')
        mm.make(cells, all_cells)


