import sys,sqlite3
from pathlib import Path
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root))
from app import create_app
path=root/'demonstracao.db';app=create_app(dict(DATABASE=str(path),AUTH_REQUIRED=False))
with sqlite3.connect(path) as db:
 if db.execute('SELECT COUNT(*) FROM demandas').fetchone()[0]==0:
  db.execute("UPDATE usuarios SET nome='Ana Souza',email='ana@example.test' WHERE id=1")
  for name,email in [('Bruno Costa','bruno@example.test'),('Carla Lima','carla@example.test')]:db.execute("INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES(?,?,'unused','colaborador')",(name,email))
  subjects=['Acesso à rede','Troca de equipamento','Atualização do cadastro','Revisão de relatório','Instalação de aplicativo','Ajuste de impressora','Suporte ao atendimento']
  for i in range(63):db.execute("INSERT INTO demandas(titulo,descricao,solicitante,solicitante_id,status,prioridade,responsavel_id,data_criacao,prazo) VALUES(?,?,?,?,?,?,?,?,?)",(f'{subjects[i%7]} {i+1:02}','Registro fictício para validação da Sprint 3.','Ana Souza',1,'aberta' if i<32 else 'concluida','alta' if i<22 else 'baixa',3 if i<27 else None,'2026-09-22 10:00:00','2026-10-15'))
app.run(port=5053,host='127.0.0.1',debug=False)
