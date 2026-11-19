"""Inline, lazy native details. Each table owns its expansion and scroll state."""
from hashlib import sha256
from html import escape
import json

import streamlit as st
import streamlit.components.v2 as components

JS = r'''
export default function({data, parentElement, setStateValue}) {
  const slot='fc-inline:'+data.key+':'+data.scope;
  let saved;try{saved=JSON.parse(sessionStorage.getItem(slot)||'{}')}catch{saved={}}
  const open=new Set(saved.open||[]), requested=new Set(data.loaded);
  for(const old of parentElement.querySelectorAll('[data-inline-table]'))old.remove();
  const box=document.createElement('div');box.dataset.inlineTable=data.key;box.innerHTML=data.html;parentElement.appendChild(box);
  const viewport=box.querySelector('.wb-tree');
  for(const el of box.querySelectorAll('details[data-node]')) el.open=open.has(el.dataset.node);
  const store=()=>sessionStorage.setItem(slot,JSON.stringify({open:[...open],requested:[...requested],left:viewport?.scrollLeft||0,top:viewport?.scrollTop||0}));
  const toggle=e=>{
    const el=e.target;if(!el.matches('details[data-node]'))return;
    el.open?open.add(el.dataset.node):open.delete(el.dataset.node);store();
    if(el.open && el.dataset.load==='yes' && !requested.has(el.dataset.node)){
      requested.add(el.dataset.node);store();
      setStateValue('requested',{scope:data.scope,nodes:[...requested]});
    }
  };
  box.addEventListener('toggle',toggle,true);
  if(viewport){viewport.scrollLeft=saved.left||0;viewport.scrollTop=saved.top||0;viewport.addEventListener('scroll',store);}
  return ()=>{box.removeEventListener('toggle',toggle,true);box.remove();};
}
'''

COMPONENT = components.component('facecode_inline_rows', js=JS)


def scope_id(model, period, paths, extra=None):
    value=[model.wb_detail['source_snapshots'],period,list(paths),extra]
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()


def node_id(path):
    return json.dumps(path,ensure_ascii=False,separators=(',',':'))


def requested(key, scope):
    value=st.session_state.get('inline_'+key,{})
    state=value.get('requested') or {}
    return set(state.get('nodes',[])) if state.get('scope')==scope else set()


def attributes(path, loaded=False):
    return f'data-node="{escape(node_id(path),quote=True)}" data-load="{"no" if loaded else "yes"}"'


def mount(html,key,scope,loaded):
    COMPONENT(data={'html':html,'key':key,'scope':scope,'loaded':list(loaded)},
              default={'requested':{'scope':scope,'nodes':[]}},key='inline_'+key,
              on_requested_change=lambda:None)
