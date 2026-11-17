'use strict';
(() => {
 let token = '';
 const el = id => document.getElementById(id);
 const show = (response, body) => {
  el('api-status').textContent = `HTTP ${response.status} · Requisição ${response.headers.get('X-Request-ID') || ''}`;
  el('api-output').textContent = body ? JSON.stringify(body, null, 2) : 'Operação concluída sem corpo de resposta.';
 };
 async function send(path, options) {
  const response = await fetch('/api/v1' + path, {...options, credentials:'omit', redirect:'error'});
  return {response, body:response.status === 204 ? null : await response.json()};
 }
 el('api-login').addEventListener('submit', async event => {
  event.preventDefault();
  try {
   const senha=el('api-password').value;el('api-password').value='';
   const {response,body}=await send('/auth/token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:el('api-email').value,senha})});
   if(response.ok){token=body.data.access_token;el('api-session').textContent=`Conectado · Perfil ${body.data.usuario.perfil} · Token expira em ${body.data.expires_in} segundos.`;body.data.access_token='[token oculto]';}
   else{token='';el('api-session').textContent='Conexão recusada.';}show(response,body);
  } catch(_){el('api-status').textContent='Não foi possível conectar à API.';}
 });
 el('api-revoke').addEventListener('click', async()=>{
  if(!token){el('api-session').textContent='Nenhum token conectado.';return;}
  try{const {response,body}=await send('/auth/token',{method:'DELETE',headers:{Authorization:'Bearer '+token}});show(response,body);if(response.ok||response.status===401){token='';el('api-session').textContent='Token revogado ou expirado. Conecte novamente para continuar.';}}
  catch(_){el('api-status').textContent='Não foi possível revogar. Tente novamente.';}
 });
 el('api-call').addEventListener('submit',async event=>{
  event.preventDefault();const path=el('api-path').value;
  if(!/^\/(demandas(?:\/\d+)?|usuarios)(?:\?[^#]*)?$/.test(path)){el('api-status').textContent='Use /demandas, /demandas/ID ou /usuarios e filtros opcionais.';return;}
  const method=el('api-method').value;if(method==='DELETE'&&!window.confirm('Excluir esta demanda do banco atual?'))return;
  try{const options={method,headers:{Authorization:'Bearer '+token}};if(['POST','PATCH'].includes(method)){options.headers['Content-Type']='application/json';options.body=JSON.stringify(JSON.parse(el('api-body').value));}
   const {response,body}=await send(path,options);show(response,body);if(response.status===401){token='';el('api-session').textContent='Token ausente, expirado ou revogado. Conecte novamente.';}}
  catch(_){el('api-status').textContent='Confira o JSON e a conexão com o sistema.';}
 });
})();
