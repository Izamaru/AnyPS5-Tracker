import copy
from datetime import datetime, timedelta, timezone
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tracker


def fake(done=2, total=3, old_names=('a', 'b')):
    return {
        'libraries': {'done': done, 'total': total, 'groups': [
            {'name': 'libSceAgc', 'done': done, 'todo': total - done,
             'done_names': list(old_names)}]},
        'shaders': {'done': 2, 'total': 2, 'groups': [
            {'name': 'DS', 'done': 2, 'todo': 0, 'done_names': ['DS_ADD', 'DS_SUB']}]}
    }


def official_day(day='2026-10-18', done=2, total=8):
    return {'date': day, 'libraries': {'done': done, 'total': total},
            'shaders': {'done': 2, 'total': 2}}


class TrackerTests(unittest.TestCase):
    def test_compact(self):
        d = tracker.compact_progress(fake())
        self.assertEqual(d['libraries']['percent'], 66.67)
        self.assertEqual(d['shaders']['percent'], 100.0)

    def test_diff_library_new_function(self):
        before = tracker.compact_progress(fake())
        after = tracker.compact_progress(fake(3, 3, ('a', 'b', 'c')))
        events = tracker.diff_progress(before, after)
        self.assertTrue(any('novas: c' in e['text'] for e in events))
        self.assertTrue(any('Bibliotecas:' in e['text'] for e in events))

    def test_unchanged_no_events(self):
        before = tracker.compact_progress(fake())
        self.assertFalse(tracker.diff_progress(before, copy.deepcopy(before)))

    def test_baseline_does_not_notify(self):
        current = {'progress': tracker.compact_progress(fake()),
                   'commit_shas': ['abc'], 'commits': [{'sha':'abc','message':'GPU','body':'GPU','url':'https://github.com/'}]}
        self.assertEqual(tracker.check_updates(None, current), [])

    def test_relevant_commit(self):
        p = tracker.compact_progress(fake())
        before = {'progress': p, 'commit_shas': ['a'], 'release': {'tag': 'v1'}}
        after = {'progress': p, 'commit_shas': ['b','a'],
                 'commits': [{'sha': 'b', 'message': 'Reduce VRAM pressure',
                              'body': 'Reduce VRAM pressure', 'url': 'https://github.com/b'}],
                 'release': {'tag':'v1'}}
        events = tracker.check_updates(before, after)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['kind'], 'commit')

    def test_irrelevant_commit(self):
        p = tracker.compact_progress(fake())
        before = {'progress': p, 'commit_shas': ['a'], 'release': {'tag': 'v1'}}
        after = {'progress': p, 'commit_shas': ['b','a'],
                 'commits': [{'sha': 'b', 'message': 'Fix spelling',
                              'body': 'Fix spelling', 'url': 'https://github.com/b'}],
                 'release': {'tag':'v1'}}
        self.assertEqual(tracker.check_updates(before, after), [])

    def test_release(self):
        p = tracker.compact_progress(fake())
        before = {'progress': p, 'release': {'tag': 'v0.1'}}
        after = {'progress': p, 'release': {'tag': 'v0.2', 'url':'https://github.com/release'}}
        events = tracker.check_updates(before, after)
        self.assertEqual(events[0]['kind'], 'release')

    def test_bad_totals(self):
        with self.assertRaises(ValueError):
            tracker.compact_progress(fake(5, 3))

    def test_official_history_validation_and_sorting(self):
        rows = [official_day('2026-10-19', 3), official_day('2026-10-18', 2)]
        result = tracker.compact_history(rows)
        self.assertEqual([row['date'] for row in result], ['2026-10-18', '2026-10-19'])
        self.assertEqual(result[0]['libraries']['percent'], 25.0)
        for invalid in ({}, [], [official_day(done=9)],
                        [official_day('not-a-date')], [official_day(), official_day()]):
            with self.subTest(raw=invalid), self.assertRaises(ValueError):
                tracker.compact_history(invalid)

    def test_snapshot_collects_official_history_and_preserves_cache_on_failure(self):
        responses = {
            tracker.PROGRESS_URL: fake(),
            tracker.HISTORY_JSON_URL: [official_day()],
            tracker.API_URL + '/releases?per_page=5': [],
            tracker.API_URL + '/commits?per_page=100': [],
        }
        with patch.object(tracker, 'request_json', side_effect=lambda url, token=None: responses[url]):
            snapshot = tracker.get_snapshot(None)
        self.assertEqual(snapshot['official_history'][0]['libraries']['done'], 2)
        self.assertFalse(snapshot['errors'])

        def failing_history(url, token=None):
            if url == tracker.HISTORY_JSON_URL:
                raise OSError('Sem conexão com o histórico')
            return responses[url]
        with patch.object(tracker, 'request_json', side_effect=failing_history):
            fallback = tracker.get_snapshot(snapshot)
        self.assertEqual(fallback['official_history'], snapshot['official_history'])
        self.assertIn('history.json', fallback['history_error'])
        self.assertIsNone(fallback['progress_error'])

    def test_dashboard_escapes_html(self):
        p = tracker.compact_progress(fake())
        data = {'progress': p, 'checked_at': 'agora', 'errors':[], 'release': None}
        output = tracker.render_dashboard(data, [{'kind':'commit','text':'<script>',
                                                  'url':'https://github.com/'}])
        # O painel tem um script próprio; o conteúdo do evento deve continuar texto.
        self.assertEqual(output.count('<script>'), 1)
        self.assertIn('&lt;script&gt;',output)

    def test_dashboard_keeps_all_events_and_blocks_unsafe_links(self):
        data = {'progress': tracker.compact_progress(fake()),
                'checked_at': '2026-10-19T17:00:00+00:00', 'errors': []}
        events = [{'kind': 'group', 'text': f'Biblioteca {index}',
                   'url': 'javascript:alert(1)'} for index in range(85)]
        output = tracker.render_dashboard(data, events)
        self.assertIn('Biblioteca 0 ', output)
        self.assertIn('Biblioteca 84 ', output)
        self.assertNotIn('javascript:', output)
        self.assertEqual(output.count('data-kind="group"'), 85)

    def test_history_comparison_explains_denominator_growth(self):
        current = {'progress': tracker.compact_progress(fake(3, 6)),
                   'checked_at': '2026-10-19T17:00:00+00:00', 'errors': []}
        history = [{'at': '2026-10-18T17:00:00+00:00',
                    'summary': tracker.compact_progress(fake(2, 3))},
                   {'at': current['checked_at'], 'summary': current['progress']}]
        from dashboard import history_points
        self.assertEqual(len(history_points(current, history)), 2)
        output = tracker.render_dashboard(current, [], history)
        self.assertIn('+1 funções', output)
        self.assertIn('−16', output.replace('-', '−'))
        self.assertIn('não significa perda de funções', output)
        self.assertIn('class="history-chart"', output)
        self.assertIn('2 dias', output)

    def test_daily_delta_uses_last_measurement_yesterday(self):
        current = {'progress': tracker.compact_progress(fake(6, 8)),
                   'checked_at': '2026-10-19T17:00:00+00:00', 'errors': []}
        history = [
            {'at': '2026-10-18T09:00:00+00:00', 'summary': tracker.compact_progress(fake(2, 8))},
            {'at': '2026-10-19T16:55:00+00:00', 'summary': tracker.compact_progress(fake(6, 8))},
            {'at': '2026-10-18T22:00:00+00:00', 'summary': tracker.compact_progress(fake(3, 8))},
        ]
        output = tracker.render_dashboard(current, [], history)
        self.assertIn('+3 funções', output)
        self.assertIn('vs. dia anterior', output)
        self.assertNotIn('vs. checagem anterior', output)
        self.assertIn('Última medição do dia anterior:', output)

    def test_daily_chart_deduplicates_and_prioritizes_sources(self):
        from dashboard import daily_history_points
        current = {'progress': tracker.compact_progress(fake(6, 8)),
                   'checked_at': '2026-10-19T17:00:00+00:00', 'errors': [],
                   'official_history': tracker.compact_history([
                       official_day('2026-10-18', 4), official_day('2026-10-19', 5),
                       official_day('2026-10-20', 7)])}
        history = [
            {'at': '2026-10-17T20:00:00+00:00', 'summary': tracker.compact_progress(fake(3, 8))},
            {'at': '2026-10-17T08:00:00+00:00', 'summary': tracker.compact_progress(fake(1, 8))},
            {'at': '2026-10-18T22:00:00+00:00', 'summary': tracker.compact_progress(fake(2, 8))},
            {'at': '2026-10-19T16:55:00+00:00', 'summary': tracker.compact_progress(fake(5, 8))},
        ]
        points = daily_history_points(current, history, timezone(timedelta(hours=-3)))
        self.assertEqual([row['date'] for row in points], ['2026-10-17', '2026-10-18', '2026-10-19'])
        self.assertEqual([row['summary']['libraries']['done'] for row in points], [3, 4, 6])
        self.assertEqual([row['source'] for row in points], ['local', 'official', 'current'])
        output = tracker.render_dashboard(current, [], history)
        self.assertIn('3 dias', output)
        self.assertIn('Hoje · parcial', output)
        self.assertEqual(output.count('class="chart-dot"'), 3)

    def test_daily_window_rolls_after_thirty_days(self):
        checked = datetime.fromisoformat('2026-10-22T17:00:00+00:00')
        current = {'checked_at': checked.isoformat(),
                   'progress': tracker.compact_progress(fake(6, 8)), 'errors': [],
                   'official_history': tracker.compact_history([
                       official_day((checked - timedelta(days=offset)).date().isoformat(), 4)
                       for offset in range(40, 0, -1)])}
        history = []
        for advance in (0, 1):
            current['checked_at'] = (checked + timedelta(days=advance)).isoformat()
            output = tracker.render_dashboard(current, [], history)
            first = checked + timedelta(days=advance - 29)
            removed = first - timedelta(days=1)
            self.assertIn('30 dias</span>', output)
            self.assertEqual(output.count('class="chart-dot"'), 30)
            table = re.search(r'<details class="history-table">(.*?)</details>', output)[1]
            self.assertEqual(table.count('<tr>'), 31)  # cabeçalho e 30 datas
            self.assertIn(first.strftime('%d/%m/%Y'), output)
            self.assertNotIn(removed.strftime('%d/%m/%Y'), output)
            history.append({'at': current['checked_at'], 'summary': current['progress']})
        self.assertEqual(len(current['official_history']), 40)

    def test_daily_chart_groups_repeated_queries_in_local_calendar(self):
        from dashboard import daily_history_points
        current = {'checked_at': '2026-10-20T01:00:00+00:00',
                   'progress': tracker.compact_progress(fake(6, 8)), 'errors': []}
        history = [{'at': f'2026-10-19T17:{minute:02d}:00+00:00',
                    'summary': tracker.compact_progress(fake(5, 8))} for minute in range(60)]
        points = daily_history_points(current, history, timezone(timedelta(hours=-3)))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['date'], '2026-10-19')
        self.assertEqual(points[0]['summary']['libraries']['done'], 6)
        history.append({'at': '2026-10-19T02:30:00+00:00',
                        'summary': tracker.compact_progress(fake(3, 8))})
        points = daily_history_points(current, history, timezone(timedelta(hours=-3)))
        self.assertEqual([row['date'] for row in points], ['2026-10-18', '2026-10-19'])

    def test_quantitative_chart_keeps_implementations_flat_when_declarations_grow(self):
        from dashboard import chart, chart_scale
        points = [
            {'date': '2026-10-19', 'source': 'official', 'summary': {'libraries': {'done': 4000, 'total': 4000, 'percent': 100}}},
            {'date': '2026-10-20', 'source': 'current', 'summary': {'libraries': {'done': 4000, 'total': 6600, 'percent': 60.61}}},
        ]
        output = chart(points)
        def heights(class_name):
            path = re.search(r'<polyline points="([^"]+)" class="' + class_name + '"', output)[1]
            return [float(pair.split(',')[1]) for pair in path.split()]
        implemented = heights('chart-line')
        declared = heights('chart-declared-line')
        self.assertEqual(implemented[0], implemented[1])
        self.assertLess(declared[1], declared[0])
        self.assertEqual(chart_scale(points), (8000, 2000))
        self.assertIn('8.000</text>', output)
        self.assertIn('6.600 declaradas', output)
        self.assertNotIn('%', output)

    def test_quantitative_chart_handles_zero_and_real_decreases(self):
        from dashboard import chart, chart_scale
        for values in ([(0, 0), (0, 0)], [(5, 8), (3, 8)]):
            points = [{'date': f'2026-10-{19+index}', 'source': 'official',
                       'summary': {'libraries': {'done': done, 'total': total}}}
                      for index, (done, total) in enumerate(values)]
            output = chart(points)
            path = re.search(r'<polyline points="([^"]+)" class="chart-line"', output)[1]
            heights = [float(pair.split(',')[1]) for pair in path.split()]
            self.assertTrue(all(22 <= y <= 198 for y in heights))
            self.assertGreaterEqual(chart_scale(points)[0], max(total for _, total in values))
            if values[0][0] > values[1][0]:
                self.assertGreater(heights[1], heights[0])
            else:
                self.assertEqual(heights, [198, 198])

    def test_daily_delta_does_not_substitute_an_older_day(self):
        current = {'progress': tracker.compact_progress(fake(6, 8)),
                   'checked_at': '2026-10-19T17:00:00+00:00', 'errors': []}
        history = [{'at': '2026-10-17T17:00:00+00:00',
                    'summary': tracker.compact_progress(fake(2, 8))}]
        output = tracker.render_dashboard(current, [], history)
        self.assertIn('Sem medição do dia anterior', output)
        self.assertNotIn('vs. dia anterior', output)

    def test_daily_delta_prefers_official_to_local_and_ignores_other_dates(self):
        current = {'progress': tracker.compact_progress(fake(6, 8)),
                   'checked_at': '2026-10-19T17:00:00+00:00', 'errors': [],
                   'official_history': tracker.compact_history([
                       official_day('2026-10-18', 2), official_day('2026-10-19', 5)])}
        history = [{'at': '2026-10-18T17:00:00+00:00',
                    'summary': tracker.compact_progress(fake(3, 8))}]
        output = tracker.render_dashboard(current, [], history)
        self.assertIn('+4 funções', output)
        self.assertIn('18/10/2026 · 2 funções · histórico oficial', output)
        self.assertIn('vs. dia anterior', output)
        current['official_history'] = tracker.compact_history([official_day('2026-10-19', 5)])
        output = tracker.render_dashboard(current, [], history)
        self.assertIn('+3 funções', output)
        self.assertIn('vs. dia anterior · histórico local', output)

    def test_official_day_is_not_shifted_by_timezone_and_cache_is_identified(self):
        from dashboard import previous_day_record
        current = {'checked_at': '2026-10-20T01:00:00+00:00',
                   'official_history': tracker.compact_history([
                       official_day('2026-10-18', 2), official_day('2026-10-19', 5)])}
        record = previous_day_record(current, [], timezone(timedelta(hours=-3)))
        self.assertEqual(record['date'], '2026-10-18')

        current.update({'checked_at': '2026-10-19T17:00:00+00:00',
                        'progress': tracker.compact_progress(fake(6, 8)),
                        'errors': ['Falha ao consultar history.json'],
                        'history_error': 'Falha ao consultar history.json', 'progress_error': None})
        output = tracker.render_dashboard(current, [], [])
        self.assertIn('+4 funções', output)
        self.assertIn('histórico oficial (salvo)', output)
        self.assertIn('Falha ao consultar history.json', output)

    def test_previous_day_follows_local_date_and_ignores_failed_measurements(self):
        from dashboard import previous_day_record
        current = {'checked_at': '2026-10-20T01:00:00+00:00'}  # 19/10, 22h em SP.
        summary = {'libraries': {'done': 3, 'total': 8, 'percent': 37.5}}
        yesterday = {'at': '2026-10-19T02:30:00+00:00', 'summary': summary}  # 18/10, 23h30.
        today = {'at': '2026-10-19T03:10:00+00:00', 'summary': summary}
        failed = {'at': '2026-10-19T02:50:00+00:00', 'summary': summary, 'errors': ['Fonte indisponível']}
        history = [today, yesterday, failed, {'at': 'inválida', 'summary': summary}]
        local_tz = timezone(timedelta(hours=-3))
        self.assertIs(previous_day_record(current, history, local_tz), yesterday)

    def test_dashboard_missing_data_and_collection_warning(self):
        output = tracker.render_dashboard({'progress': None, 'errors': ['Falha <API>']}, [])
        self.assertIn('Falha &lt;API&gt;', output)
        self.assertIn('Coleta com avisos', output)
        self.assertNotIn('100,00%', output)
        self.assertIn('pelo menos dois dias', output)

    def test_render_only_preserves_state_and_does_not_collect(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            state, history, panel = root/'estado.json', root/'historico.jsonl', root/'painel.html'
            current = {'progress': tracker.compact_progress(fake()),
                       'checked_at': '2026-10-19T17:00:00+00:00', 'errors': []}
            tracker.atomic_json(state, current)
            original = state.read_bytes()
            with patch.object(tracker, 'STATE_FILE', state), \
                 patch.object(tracker, 'DASHBOARD_FILE', panel), \
                 patch.object(tracker, 'load_history', return_value=[]), \
                 patch.object(tracker, 'get_snapshot') as collect, \
                 patch.object(tracker, 'send_webhooks') as notify, \
                 patch.object(sys, 'argv', ['tracker.py', '--render-only']):
                self.assertEqual(tracker.run(), 0)
                collect.assert_not_called()
                notify.assert_not_called()
            self.assertTrue(panel.exists())
            self.assertEqual(state.read_bytes(), original)
            self.assertFalse(history.exists())

    def test_load_history_skips_truncated_line(self):
        with tempfile.TemporaryDirectory() as folder:
            history = Path(folder)/'historico.jsonl'
            history.write_text('{"at":"ok"}\n{"at":', encoding='utf-8')
            self.assertEqual(tracker.load_history(history), [{'at': 'ok'}])

    def test_dashboard_atomic_replace_keeps_previous_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            panel = Path(folder)/'painel.html'
            panel.write_text('painel anterior', encoding='utf-8')
            with patch.object(tracker.os, 'replace', side_effect=PermissionError('arquivo ocupado')):
                with self.assertRaises(PermissionError):
                    tracker.atomic_text(panel, 'novo painel')
            self.assertEqual(panel.read_text(encoding='utf-8'), 'painel anterior')
            self.assertEqual(list(Path(folder).iterdir()), [panel])
            tracker.atomic_text(panel, 'novo painel')
            self.assertEqual(panel.read_text(encoding='utf-8'), 'novo painel')


if __name__ == '__main__':
    unittest.main()
