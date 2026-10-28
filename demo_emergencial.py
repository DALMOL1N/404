"""Demonstração isolada com dados explicitamente fictícios."""
from database import sqlite_transaction
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from app import create_app
path=Path(__file__).with_name('demonstracao-emergencial.db')
app=create_app({'DATABASE':str(path),'AUTH_REQUIRED':False,'COMPANY_NAME':'Equipe 404 • Demonstração fictícia'})
with sqlite_transaction(path) as db:
 if not db.execute('SELECT COUNT(*) FROM demandas').fetchone()[0]:
  people=[]
  for i,name in enumerate(['Ana Teste','Bruno Teste','Carla Teste']):
   people.append(db.execute('INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES(?,?,?,?)',(name,f'demo{i}@example.test','unused','colaborador')).lastrowid)
  now=datetime.now().replace(hour=10,minute=0,second=0,microsecond=0)
  for i in range(48):
   created=now-timedelta(days=20-i%18);status=['aberta','em_andamento','concluida','aguardando','cancelada','em_analise'][i%6]
   priority=['critica','alta','media','baixa'][i%4];person=None if i%7==0 else people[i%3]
   finished=created+timedelta(days=1+i%8) if status=='concluida' else None
   deadline=(created+timedelta(days=5+i%14)).date().isoformat()
   db.execute('''INSERT INTO demandas(titulo,descricao,solicitante,solicitante_id,status,prioridade,responsavel_id,prazo,data_criacao,data_atualizacao,data_conclusao)
                VALUES(?,?,?,1,?,?,?,?,?,?,?)''',(f'Demanda demonstrativa {i+1:02}','Registro fictício para validar o dashboard','Administrador',status,priority,person,deadline,created.isoformat(' '),(finished or created).isoformat(' '),finished.isoformat(' ') if finished else None))
if __name__=='__main__':app.run(host='127.0.0.1',port=5054,debug=False)
