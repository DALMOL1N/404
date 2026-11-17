"""Filtro de vencimento com datas fixas, combinações e paginação."""
import re
import tempfile
import unittest
from datetime import date, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from app import create_app
from database import sqlite_transaction


class DeadlineFilterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'deadlines.db'
        self.today = date(2026, 10, 27)
        self.app = create_app(dict(TESTING=True, AUTH_REQUIRED=False,
                                   DATABASE=str(self.path), REPORT_TODAY=self.today))
        self.client = self.app.test_client()
        with sqlite_transaction(self.path) as db:
            self.person = db.execute("INSERT INTO usuarios(nome,email,senha_hash,perfil) VALUES('Teste','prazo@example.test','unused','colaborador')").lastrowid
        self.past = self.add('Ontem', -1)
        self.analysis = self.add('Antiga em análise', -3, 'em_analise')
        self.today_id = self.add('Hoje', 0)
        self.tomorrow = self.add('Amanhã', 1)
        self.seventh = self.add('Sétimo dia', 7, 'aguardando')
        self.eighth = self.add('Oitavo dia', 8)
        self.no_deadline = self.add('Sem prazo', None)
        self.blank = self.add('Prazo vazio legado', '')
        self.closed = self.add('Concluída atrasada', -1, 'concluida')
        self.cancelled = self.add('Cancelada hoje', 0, 'cancelada')
        self.closed_future = self.add('Concluída futura', 1, 'concluida')

    def add(self, title, offset, status='aberta'):
        deadline = ((self.today + timedelta(days=offset)).isoformat()
                    if isinstance(offset, int) else offset)
        with sqlite_transaction(self.path) as db:
            return db.execute("""INSERT INTO demandas(titulo,descricao,solicitante,
                solicitante_id,status,prioridade,responsavel_id,prazo,data_criacao)
                VALUES(?,?,?,1,?,'alta',?,?,?)""",
                (title, 'Descrição para teste', 'Administrador', status,
                 self.person, deadline, self.today.isoformat())).lastrowid

    def response(self, **query):
        result = self.client.get('/demandas?' + urlencode(query))
        self.assertEqual(result.status_code, 200)
        return result.get_data(as_text=True)

    def ids(self, **query):
        return [int(value) for value in re.findall(r'<span class="id-badge">#(\d+)',
                                                   self.response(**query))]

    def test_todos_preserva_concluidas_canceladas_e_sem_prazo(self):
        ids = self.ids(por_pagina=50)
        self.assertEqual(len(ids), 11)
        self.assertTrue({self.closed, self.cancelled, self.no_deadline}.issubset(ids))

    def test_atrasadas_exclui_hoje_futuras_sem_prazo_e_encerradas(self):
        self.assertEqual(set(self.ids(vencimento='atrasadas')), {self.past, self.analysis})

    def test_hoje_exclui_canceladas(self):
        self.assertEqual(self.ids(vencimento='hoje'), [self.today_id])

    def test_proximos_sete_dias_limites_inclusivos_e_sem_hoje(self):
        self.assertEqual(set(self.ids(vencimento='proximos_7_dias')),
                         {self.tomorrow, self.seventh})

    def test_sem_prazo_aceita_null_e_vazio_legado(self):
        self.assertEqual(set(self.ids(vencimento='sem_prazo')), {self.no_deadline, self.blank})

    def test_sem_prazo_pode_incluir_concluida(self):
        closed_without = self.add('Concluída sem prazo', None, 'concluida')
        self.assertEqual(self.ids(vencimento='sem_prazo', status='concluida'), [closed_without])

    def test_combinacao_paginacao_e_links_preservam_todos_filtros(self):
        expected = {self.add(f'Combinada {i:02}', 2) for i in range(12)}
        query = dict(q='Combinada', vencimento='proximos_7_dias', status='aberta',
                     prioridade='alta', responsavel=self.person, solicitante=1,
                     ordenar='titulo', por_pagina=10)
        body = self.response(**query)
        self.assertIn('12 registros encontrados', body)
        link = re.search(r'href="([^"]+)" aria-label="Próxima página"', body).group(1)
        target = parse_qs(urlsplit(unescape(link)).query)
        self.assertEqual(target, {**{k: [str(v)] for k, v in query.items()}, 'pagina': ['2']})
        ids = self.ids(**query) + self.ids(**query, pagina=2)
        self.assertEqual(len(ids), 12)
        self.assertEqual(set(ids), expected)
        self.assertIn('name="vencimento" value="proximos_7_dias"', body)
        self.assertIn('value="proximos_7_dias" selected', body)
        # Aplicar o formulário principal volta à primeira página.
        main_form = body.split('<form class="filter-panel"', 1)[1].split('</form>', 1)[0]
        self.assertNotIn('name="pagina"', main_form)
        self.assertIn('class="filter-clear" href="/demandas"', body)

    def test_filtro_invalido_e_tentativa_de_injecao_retornam_400(self):
        for value in ['invalido', "hoje' OR 1=1 --", 'HOJE']:
            self.assertEqual(self.client.get('/demandas?' + urlencode({'vencimento': value})).status_code, 400)
        self.assertEqual(len(self.ids(por_pagina=50)), 11)

    def test_intervalo_atravessa_ano_e_mes(self):
        self.today = date(2026, 12, 28)
        self.app.config['REPORT_TODAY'] = self.today
        first = self.add('Virada amanhã', 1)
        last = self.add('Virada sétimo', 7)
        self.add('Virada fora', 8)
        self.assertEqual(set(self.ids(vencimento='proximos_7_dias')), {first, last})

    def test_status_encerrado_com_filtro_de_vencimento_retorna_vazio(self):
        body = self.response(status='concluida', vencimento='atrasadas')
        self.assertIn('Nenhuma demanda encontrada', body)
        self.assertIn('0 registros encontrados', body)


if __name__ == '__main__':
    unittest.main()
