"""Streaming export of the exact prepared web frames; no Excel business formulas."""
from io import BytesIO
from fc_format import DEMO_LABEL, rate
import re,json,tempfile
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font,PatternFill
from openpyxl.utils import get_column_letter
def excel(sheets,metadata=None):
 wb=Workbook(write_only=True);used=set()
 if metadata:sheets=[('Периоды и методики',pd.DataFrame([{'Параметр':k,'Значение':str(v)} for k,v in metadata.items()]))]+list(sheets)
 for name,frame in sheets:
  title=re.sub(r'[\\/*?:\[\]]',' ',str(name)).strip()[:31] or 'Данные';original=title;n=1
  while title in used:n+=1;tail=' '+str(n);title=original[:31-len(tail)]+tail
  used.add(title);ws=wb.create_sheet(title);ws.freeze_panes='A3';ws.append([DEMO_LABEL]);header=[]
  for i,label in enumerate(frame.columns,1):
   cell=WriteOnlyCell(ws,str(label));cell.data_type='s';cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='263950');header.append(cell);ws.column_dimensions[get_column_letter(i)].width=min(55,max(16,len(str(label))+3))
  if header:ws.append(header)
  for row in frame.itertuples(index=False,name=None):
   metric = str(row[frame.columns.get_loc("Показатель")]) if "Показатель" in frame else ""
   cells=[]
   for label,v in zip(frame.columns,row):
    if isinstance(v,(dict,list,set,tuple)):v=json.dumps(list(v) if isinstance(v,set) else v,ensure_ascii=False,default=str)
    if v is None or not isinstance(v,str) and pd.isna(v):v=None
    if hasattr(v,'item'):v=v.item()
    cell=WriteOnlyCell(ws,v)
    if isinstance(v,str):cell.data_type='s'
    elif isinstance(v,(int,float)) and not isinstance(v,bool):cell.number_format='0.00' if rate(str(label)) or rate(metric) or str(label).startswith('H7 ') else '#,##0'
    cells.append(cell)
   ws.append(cells)
  if len(frame.columns):ws.auto_filter.ref=f'A2:{get_column_letter(len(frame.columns))}{len(frame)+2}'
 output=BytesIO();wb.save(output);return output.getvalue()

