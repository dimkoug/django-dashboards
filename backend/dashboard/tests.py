from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Activity, Column, Comment, DashBoard, Label, Todo
from .serializers import parse_mention_usernames, resolve_mentioned_users

User = get_user_model()


def make_user(username, password='Str0ngPass!9'):
    return User.objects.create_user(username=username, password=password)


class AuthTests(APITestCase):
    def test_register_then_login(self):
        r = self.client.post('/api/auth/register/', {
            'username': 'alice', 'password': 'Str0ngPass!9'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        r = self.client.post('/api/auth/token/', {
            'username': 'alice', 'password': 'Str0ngPass!9'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('access', r.data)

    def test_weak_password_rejected(self):
        r = self.client.post('/api/auth/register/', {
            'username': 'bob', 'password': '123'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_rejected(self):
        self.assertEqual(self.client.get('/api/dashboards/').status_code,
                         status.HTTP_401_UNAUTHORIZED)


class ApiTestCase(APITestCase):
    def auth(self, user):
        self.client.force_authenticate(user=user)


class DashboardTests(ApiTestCase):
    def setUp(self):
        self.owner = make_user('owner')
        self.member = make_user('member')
        self.other = make_user('other')

    def test_crud_and_pagination_envelope(self):
        self.auth(self.owner)
        r = self.client.post('/api/dashboards/', {'name': 'D'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        r = self.client.get('/api/dashboards/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        # Paginated envelope.
        self.assertIn('count', r.data)
        self.assertIn('results', r.data)
        self.assertEqual(r.data['count'], 1)
        self.assertTrue(r.data['results'][0]['is_owner'])

    def test_sharing_visibility_and_owner_only_guard(self):
        self.auth(self.owner)
        did = self.client.post('/api/dashboards/', {'name': 'S'},
                               format='json').data['id']
        # Non-member cannot see it.
        self.auth(self.other)
        self.assertEqual(self.client.get(f'/api/dashboards/{did}/').status_code,
                         status.HTTP_404_NOT_FOUND)
        # Owner shares with member.
        self.auth(self.owner)
        r = self.client.patch(f'/api/dashboards/{did}/',
                              {'users': [self.member.id]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        # Member now sees it, flagged not-owner.
        self.auth(self.member)
        r = self.client.get(f'/api/dashboards/{did}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data['is_owner'])
        # Member cannot delete or re-share (owner only).
        self.assertEqual(
            self.client.delete(f'/api/dashboards/{did}/').status_code,
            status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.patch(f'/api/dashboards/{did}/', {'users': []},
                              format='json').status_code,
            status.HTTP_403_FORBIDDEN)

    def test_member_can_collaborate(self):
        self.auth(self.owner)
        did = self.client.post('/api/dashboards/', {'name': 'C'},
                               format='json').data['id']
        self.client.patch(f'/api/dashboards/{did}/',
                          {'users': [self.member.id]}, format='json')
        self.auth(self.member)
        r = self.client.post('/api/columns/',
                             {'dashboard': did, 'name': 'col'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)


class TodoRuleTests(ApiTestCase):
    def setUp(self):
        self.u = make_user('u')
        self.auth(self.u)
        self.d = DashBoard.objects.create(user=self.u, name='D')
        self.c1 = Column.objects.create(dashboard=self.d, name='c1')
        self.c2 = Column.objects.create(dashboard=self.d, name='c2')
        self.d2 = DashBoard.objects.create(user=self.u, name='D2')
        self.cx = Column.objects.create(dashboard=self.d2, name='cx')

    def test_dashboard_field_renamed(self):
        r = self.client.post('/api/columns/',
                             {'dashboard': self.d.id, 'name': 'n'},
                             format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn('dashboard', r.data)
        self.assertNotIn('dasboard', r.data)

    def test_end_after_start_validation(self):
        r = self.client.post('/api/todos/', {
            'column': self.c1.id, 'name': 't',
            'start_date': '2026-06-10T10:00:00Z',
            'end_date': '2026-06-10T09:00:00Z'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('end_date', r.data)

    def test_same_dashboard_move_only(self):
        t = Todo.objects.create(column=self.c1, name='t')
        ok = self.client.patch(f'/api/todos/{t.id}/',
                               {'column': self.c2.id}, format='json')
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        bad = self.client.patch(f'/api/todos/{t.id}/',
                                {'column': self.cx.id}, format='json')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)


class FilterTests(ApiTestCase):
    def setUp(self):
        self.u = make_user('fu')
        self.assignee = make_user('fa')
        self.auth(self.u)
        d = DashBoard.objects.create(user=self.u, name='D')
        c = Column.objects.create(dashboard=d, name='c')
        self.done = Todo.objects.create(column=c, name='done one',
                                        completed=True)
        self.open = Todo.objects.create(column=c, name='open one')
        self.open.users.add(self.assignee)

    def test_completed_assignee_search(self):
        r = self.client.get('/api/todos/?completed=true')
        self.assertEqual([t['name'] for t in r.data['results']], ['done one'])
        r = self.client.get(f'/api/todos/?assignee={self.assignee.id}')
        self.assertEqual([t['name'] for t in r.data['results']], ['open one'])
        r = self.client.get('/api/todos/?search=done')
        self.assertEqual([t['name'] for t in r.data['results']], ['done one'])

    def test_assigned_endpoint(self):
        self.auth(self.assignee)
        r = self.client.get('/api/todos/assigned/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual([t['name'] for t in r.data], ['open one'])


class LabelAndDetailTests(ApiTestCase):
    def setUp(self):
        self.u = make_user('lu')
        self.auth(self.u)
        self.d = DashBoard.objects.create(user=self.u, name='D')
        self.col = Column.objects.create(dashboard=self.d, name='c')
        self.other_d = DashBoard.objects.create(user=self.u, name='D2')

    def test_label_crud_and_color_validation(self):
        r = self.client.post('/api/labels/', {
            'dashboard': self.d.id, 'name': 'bug', 'color': '#ff0000'},
            format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        bad = self.client.post('/api/labels/', {
            'dashboard': self.d.id, 'name': 'x', 'color': 'red'},
            format='json')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        r = self.client.get('/api/labels/')
        self.assertEqual(r.data['count'], 1)

    def test_priority_default_and_set(self):
        r = self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 't'}, format='json')
        self.assertEqual(r.data['priority'], 'medium')
        r = self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 't2', 'priority': 'high'},
            format='json')
        self.assertEqual(r.data['priority'], 'high')

    def test_description_markdown_sanitized(self):
        r = self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 't',
            'description': '**bold** <script>alert(1)</script>'},
            format='json')
        html = r.data['description_html']
        self.assertIn('<strong>bold</strong>', html)
        self.assertNotIn('<script>', html)

    def test_label_must_match_dashboard(self):
        good = Label.objects.create(dashboard=self.d, name='g')
        bad = Label.objects.create(dashboard=self.other_d, name='b')
        ok = self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 't', 'labels': [good.id]},
            format='json')
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
        rej = self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 't2', 'labels': [bad.id]},
            format='json')
        self.assertEqual(rej.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('labels', rej.data)

    def test_priority_and_label_filters(self):
        lbl = Label.objects.create(dashboard=self.d, name='L')
        hi = Todo.objects.create(column=self.col, name='hi',
                                 priority='high')
        hi.labels.add(lbl)
        Todo.objects.create(column=self.col, name='lo', priority='low')
        r = self.client.get('/api/todos/?priority=high')
        self.assertEqual([t['name'] for t in r.data['results']], ['hi'])
        r = self.client.get(f'/api/todos/?label={lbl.id}')
        self.assertEqual([t['name'] for t in r.data['results']], ['hi'])


class ReorderTests(ApiTestCase):
    def setUp(self):
        self.u = make_user('ru')
        self.outsider = make_user('ro')
        self.auth(self.u)
        self.d = DashBoard.objects.create(user=self.u, name='D')
        self.col = Column.objects.create(dashboard=self.d, name='c')
        self.t1 = Todo.objects.create(column=self.col, name='t1')
        self.t2 = Todo.objects.create(column=self.col, name='t2')
        self.t3 = Todo.objects.create(column=self.col, name='t3')

    def test_create_appends_position(self):
        # Created in order -> positions 0,1,2.
        self.assertEqual(
            [self.t1.position, self.t2.position, self.t3.position],
            [0, 1, 2])

    def test_reorder_persists_positions(self):
        r = self.client.post('/api/todos/reorder/', {
            'column': self.col.id,
            'order': [self.t3.id, self.t1.id, self.t2.id]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.t1.refresh_from_db()
        self.t2.refresh_from_db()
        self.t3.refresh_from_db()
        self.assertEqual(self.t3.position, 0)
        self.assertEqual(self.t1.position, 1)
        self.assertEqual(self.t2.position, 2)

    def test_reorder_rejects_incomplete_set(self):
        r = self.client.post('/api/todos/reorder/', {
            'column': self.col.id, 'order': [self.t1.id]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reorder_other_users_column_404(self):
        self.auth(self.outsider)
        r = self.client.post('/api/todos/reorder/', {
            'column': self.col.id,
            'order': [self.t1.id, self.t2.id, self.t3.id]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


class CommentActivityTests(ApiTestCase):
    def setUp(self):
        self.owner = make_user('cowner')
        self.member = make_user('cmember')
        self.outsider = make_user('coutsider')
        self.d = DashBoard.objects.create(user=self.owner, name='D')
        self.d.users.add(self.member)
        self.col = Column.objects.create(dashboard=self.d, name='c')
        self.todo = Todo.objects.create(column=self.col, name='task')

    def test_member_can_comment_outsider_cannot(self):
        self.auth(self.member)
        r = self.client.post('/api/comments/', {
            'todo': self.todo.id, 'body': 'hi'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['author_username'], 'cmember')
        self.auth(self.outsider)
        r = self.client.post('/api/comments/', {
            'todo': self.todo.id, 'body': 'x'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_comment_list_filtered_by_todo(self):
        self.auth(self.owner)
        self.client.post('/api/comments/', {
            'todo': self.todo.id, 'body': 'a'}, format='json')
        r = self.client.get(f'/api/comments/?todo={self.todo.id}')
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['body'], 'a')

    def test_delete_only_author_or_owner(self):
        self.auth(self.member)
        cid = self.client.post('/api/comments/', {
            'todo': self.todo.id, 'body': 'm'}, format='json').data['id']
        # Outsider can't even see it; another member who isn't author:
        other = make_user('cother')
        self.d.users.add(other)
        self.auth(other)
        self.assertEqual(
            self.client.delete(f'/api/comments/{cid}/').status_code,
            status.HTTP_403_FORBIDDEN)
        # Dashboard owner can delete anyone's comment.
        self.auth(self.owner)
        self.assertEqual(
            self.client.delete(f'/api/comments/{cid}/').status_code,
            status.HTTP_204_NO_CONTENT)

    def test_activity_recorded_and_scoped(self):
        self.auth(self.owner)
        self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 'newt'}, format='json')
        self.client.post('/api/comments/', {
            'todo': self.todo.id, 'body': 'c'}, format='json')
        verbs = set(
            Activity.objects.filter(dashboard=self.d)
            .values_list('verb', flat=True))
        self.assertIn('created_todo', verbs)
        self.assertIn('commented', verbs)
        r = self.client.get(f'/api/activity/?dashboard={self.d.id}')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r.data['count'], 2)
        # Outsider sees nothing.
        self.auth(self.outsider)
        r = self.client.get(f'/api/activity/?dashboard={self.d.id}')
        self.assertEqual(r.data['count'], 0)


class AccountSecurityTests(ApiTestCase):
    def setUp(self):
        self.u = make_user('acct')

    def test_users_search_required(self):
        make_user('findme')
        self.auth(self.u)
        # No / short search -> empty (not enumerable).
        self.assertEqual(self.client.get('/api/users/').data['count'], 0)
        self.assertEqual(
            self.client.get('/api/users/?search=f').data['count'], 0)
        r = self.client.get('/api/users/?search=find')
        self.assertEqual(
            [x['username'] for x in r.data['results']], ['findme'])

    def test_me_get_and_patch(self):
        self.auth(self.u)
        r = self.client.get('/api/auth/me/')
        self.assertEqual(r.data['username'], 'acct')
        r = self.client.patch('/api/auth/me/',
                              {'email': 'a@b.com', 'username': 'hacked'},
                              format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['email'], 'a@b.com')
        self.assertEqual(r.data['username'], 'acct')  # read-only

    def test_change_password(self):
        self.auth(self.u)
        bad = self.client.post('/api/auth/change-password/', {
            'old_password': 'wrong', 'new_password': 'Str0ngPass!2'},
            format='json')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        ok = self.client.post('/api/auth/change-password/', {
            'old_password': 'Str0ngPass!9',
            'new_password': 'N3w!Str0ngPass'}, format='json')
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.u.refresh_from_db()
        self.assertTrue(self.u.check_password('N3w!Str0ngPass'))

    def test_logout_blacklists_refresh(self):
        r = self.client.post('/api/auth/token/', {
            'username': 'acct', 'password': 'Str0ngPass!9'}, format='json')
        refresh = r.data['refresh']
        # Refresh works before logout.
        self.assertEqual(
            self.client.post('/api/auth/token/refresh/',
                             {'refresh': refresh}, format='json').status_code,
            status.HTTP_200_OK)
        self.auth(self.u)
        out = self.client.post('/api/auth/logout/',
                               {'refresh': refresh}, format='json')
        self.assertEqual(out.status_code, status.HTTP_205_RESET_CONTENT)
        # Blacklisted -> refresh now rejected.
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.post('/api/auth/token/refresh/',
                             {'refresh': refresh}, format='json').status_code,
            status.HTTP_401_UNAUTHORIZED)

    def test_nested_assignees_and_members(self):
        self.auth(self.u)
        other = make_user('teammate')
        d = DashBoard.objects.create(user=self.u, name='D')
        d.users.add(other)
        col = Column.objects.create(dashboard=d, name='c')
        t = Todo.objects.create(column=col, name='t')
        t.users.add(other)
        r = self.client.get('/api/todos/')
        todo = r.data['results'][0]
        self.assertEqual(
            [a['username'] for a in todo['assignees']], ['teammate'])
        r = self.client.get('/api/dashboards/')
        dash = r.data['results'][0]
        self.assertEqual(
            [m['username'] for m in dash['members']], ['teammate'])


class AttachmentTests(ApiTestCase):
    def setUp(self):
        self.owner = make_user('aowner')
        self.member = make_user('amember')
        self.outsider = make_user('aoutsider')
        self.d = DashBoard.objects.create(user=self.owner, name='D')
        self.d.users.add(self.member)
        self.col = Column.objects.create(dashboard=self.d, name='c')
        self.todo = Todo.objects.create(column=self.col, name='task')

    def _upload(self, name='note.txt', content=b'hello'):
        return self.client.post('/api/attachments/', {
            'todo': self.todo.id,
            'file': SimpleUploadedFile(name, content),
        }, format='multipart')

    def test_member_uploads_outsider_cannot(self):
        self.auth(self.member)
        r = self._upload()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['original_name'], 'note.txt')
        self.assertEqual(r.data['size'], 5)
        self.assertIn('/media/', r.data['file_url'])
        self.auth(self.outsider)
        self.assertEqual(self._upload().status_code,
                         status.HTTP_400_BAD_REQUEST)

    def test_list_filtered_by_todo_and_activity(self):
        self.auth(self.member)
        self._upload()
        r = self.client.get(f'/api/attachments/?todo={self.todo.id}')
        self.assertEqual(r.data['count'], 1)
        self.assertTrue(
            Activity.objects.filter(dashboard=self.d,
                                    verb='attached').exists())

    def test_delete_only_uploader_or_owner(self):
        self.auth(self.member)
        aid = self._upload().data['id']
        another = make_user('amember2')
        self.d.users.add(another)
        self.auth(another)
        self.assertEqual(
            self.client.delete(f'/api/attachments/{aid}/').status_code,
            status.HTTP_403_FORBIDDEN)
        self.auth(self.owner)
        self.assertEqual(
            self.client.delete(f'/api/attachments/{aid}/').status_code,
            status.HTTP_204_NO_CONTENT)


class MentionTests(ApiTestCase):
    def setUp(self):
        self.owner = make_user('mowner')
        self.member = make_user('mmember')
        self.outsider = make_user('moutsider')
        self.d = DashBoard.objects.create(user=self.owner, name='D')
        self.d.users.add(self.member)
        self.col = Column.objects.create(dashboard=self.d, name='c')
        self.todo = Todo.objects.create(column=self.col, name='task')

    def test_parse_mentions(self):
        self.assertEqual(
            sorted(parse_mention_usernames('hi @mmember and @ghost!')),
            ['ghost', 'mmember'])
        self.assertEqual(parse_mention_usernames('no mentions'), [])

    def test_mention_resolves_only_dashboard_members(self):
        self.auth(self.owner)
        r = self.client.post('/api/comments/', {
            'todo': self.todo.id,
            'body': 'ping @mmember @moutsider @ghost'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        comment = Comment.objects.get(id=r.data['id'])
        resolved = {u.username for u in resolve_mentioned_users(comment)}
        # Only the dashboard member; outsider & nonexistent excluded.
        self.assertEqual(resolved, {'mmember'})

    def test_self_mention_excluded(self):
        self.auth(self.member)
        r = self.client.post('/api/comments/', {
            'todo': self.todo.id, 'body': 'note to @mmember self'},
            format='json')
        comment = Comment.objects.get(id=r.data['id'])
        self.assertEqual(list(resolve_mentioned_users(comment)), [])


class StatsTests(ApiTestCase):
    def setUp(self):
        from django.utils import timezone
        self.owner = make_user('sowner')
        self.outsider = make_user('soutsider')
        self.a = make_user('sa')
        self.d = DashBoard.objects.create(user=self.owner, name='D')
        self.c1 = Column.objects.create(dashboard=self.d, name='c1')
        self.c2 = Column.objects.create(dashboard=self.d, name='c2')
        past = timezone.now() - timezone.timedelta(days=2)
        # 4 todos: 1 completed(high), 1 overdue(low), 2 open(medium)
        Todo.objects.create(column=self.c1, name='done',
                            completed=True, priority='high')
        od = Todo.objects.create(column=self.c1, name='late',
                                 priority='low', end_date=past)
        od.users.add(self.a)
        Todo.objects.create(column=self.c2, name='o1', priority='medium')
        Todo.objects.create(column=self.c2, name='o2', priority='medium')

    def test_stats(self):
        self.auth(self.owner)
        r = self.client.get(f'/api/dashboards/{self.d.id}/stats/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        d = r.data
        self.assertEqual(d['total'], 4)
        self.assertEqual(d['completed'], 1)
        self.assertEqual(d['open'], 3)
        self.assertEqual(d['overdue'], 1)
        self.assertEqual(d['by_priority'],
                         {'low': 1, 'medium': 2, 'high': 1})
        cols = {c['name']: (c['total'], c['completed']) for c in
                d['by_column']}
        self.assertEqual(cols, {'c1': (2, 1), 'c2': (2, 0)})
        self.assertEqual(d['by_assignee'],
                         [{'username': 'sa', 'count': 1}])

    def test_stats_access_controlled(self):
        self.auth(self.outsider)
        r = self.client.get(f'/api/dashboards/{self.d.id}/stats/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


class SearchAndSavedViewTests(ApiTestCase):
    def setUp(self):
        self.owner = make_user('qowner')
        self.member = make_user('qmember')
        self.outsider = make_user('qoutsider')
        self.d = DashBoard.objects.create(user=self.owner, name='D')
        self.d.users.add(self.member)
        self.col = Column.objects.create(dashboard=self.d, name='c')
        self.todo = Todo.objects.create(
            column=self.col, name='deploy pipeline',
            description='blue-green release')
        from .models import Comment
        Comment.objects.create(todo=self.todo, author=self.owner,
                                body='needs a rollback plan')

    def test_search_scoped(self):
        self.auth(self.member)
        r = self.client.get('/api/search/?q=pipeline')
        self.assertEqual([t['name'] for t in r.data['todos']],
                         ['deploy pipeline'])
        r = self.client.get('/api/search/?q=rollback')
        self.assertEqual(len(r.data['comments']), 1)
        # description match
        r = self.client.get('/api/search/?q=blue-green')
        self.assertEqual(len(r.data['todos']), 1)
        # too short
        self.assertEqual(self.client.get('/api/search/?q=a').data['todos'],
                         [])
        # outsider sees nothing
        self.auth(self.outsider)
        r = self.client.get('/api/search/?q=pipeline')
        self.assertEqual(r.data['todos'], [])
        self.assertEqual(r.data['comments'], [])

    def test_saved_view_crud_is_private(self):
        self.auth(self.owner)
        r = self.client.post('/api/saved-views/', {
            'name': 'My overdue',
            'params': {'status': 'open', 'priority': 'high'}},
            format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        vid = r.data['id']
        self.assertEqual(self.client.get('/api/saved-views/').data['count'],
                         1)
        # Other user can't see or fetch it.
        self.auth(self.member)
        self.assertEqual(self.client.get('/api/saved-views/').data['count'],
                         0)
        self.assertEqual(
            self.client.get(f'/api/saved-views/{vid}/').status_code,
            status.HTTP_404_NOT_FOUND)
        # Duplicate name for same user rejected.
        self.auth(self.owner)
        dup = self.client.post('/api/saved-views/', {
            'name': 'My overdue', 'params': {}}, format='json')
        self.assertEqual(dup.status_code, status.HTTP_400_BAD_REQUEST)


class SubtaskTests(ApiTestCase):
    def setUp(self):
        self.owner = make_user('btowner')
        self.member = make_user('btmember')
        self.outsider = make_user('btoutsider')
        self.d = DashBoard.objects.create(user=self.owner, name='D')
        self.d.users.add(self.member)
        self.col = Column.objects.create(dashboard=self.d, name='c')
        self.todo = Todo.objects.create(column=self.col, name='task')

    def test_member_crud_outsider_blocked(self):
        self.auth(self.member)
        r = self.client.post('/api/subtasks/', {
            'todo': self.todo.id, 'text': 'step 1'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['position'], 0)
        sid = r.data['id']
        r2 = self.client.post('/api/subtasks/', {
            'todo': self.todo.id, 'text': 'step 2'}, format='json')
        self.assertEqual(r2.data['position'], 1)  # appended
        # toggle done
        p = self.client.patch(f'/api/subtasks/{sid}/',
                              {'done': True}, format='json')
        self.assertTrue(p.data['done'])
        # outsider can't add
        self.auth(self.outsider)
        self.assertEqual(
            self.client.post('/api/subtasks/', {
                'todo': self.todo.id, 'text': 'x'}, format='json'
            ).status_code, status.HTTP_400_BAD_REQUEST)

    def test_summary_on_todo(self):
        self.auth(self.owner)
        for i in range(3):
            self.client.post('/api/subtasks/', {
                'todo': self.todo.id, 'text': f's{i}'}, format='json')
        first = self.client.get(
            f'/api/subtasks/?todo={self.todo.id}').data['results'][0]
        self.client.patch(f'/api/subtasks/{first["id"]}/',
                          {'done': True}, format='json')
        r = self.client.get('/api/todos/')
        todo = next(t for t in r.data['results'] if t['id'] == self.todo.id)
        self.assertEqual(todo['subtask_summary'], {'total': 3, 'done': 1})


class RecurrenceTests(ApiTestCase):
    def setUp(self):
        from django.utils import timezone
        self.tz = timezone
        self.u = make_user('rcu')
        self.auth(self.u)
        self.d = DashBoard.objects.create(user=self.u, name='D')
        self.col = Column.objects.create(dashboard=self.d, name='c')

    def _todo(self, **kw):
        start = kw.pop('start', self.tz.now())
        t = Todo.objects.create(column=self.col, name='chore',
                                start_date=start, **kw)
        return t

    def test_complete_spawns_next_daily(self):
        from .models import Subtask
        t = self._todo(recurrence='daily',
                        end_date=self.tz.now() + self.tz.timedelta(hours=2))
        t.users.add(self.u)
        Subtask.objects.create(todo=t, text='step', done=True)
        before = Todo.objects.filter(column=self.col).count()
        self.client.patch(f'/api/todos/{t.id}/', {'completed': True},
                          format='json')
        self.assertEqual(Todo.objects.filter(column=self.col).count(),
                         before + 1)
        nxt = Todo.objects.filter(column=self.col,
                                  completed=False).latest('id')
        self.assertEqual(nxt.recurrence, 'daily')
        self.assertEqual(
            nxt.start_date,
            t.start_date + self.tz.timedelta(days=1))
        self.assertEqual(list(nxt.users.all()), [self.u])
        # checklist copied unchecked
        subs = list(nxt.subtasks.all())
        self.assertEqual(len(subs), 1)
        self.assertFalse(subs[0].done)
        self.assertTrue(Activity.objects.filter(
            dashboard=self.d, verb='recurred').exists())

    def test_non_recurring_does_not_spawn(self):
        t = self._todo()
        before = Todo.objects.filter(column=self.col).count()
        self.client.patch(f'/api/todos/{t.id}/', {'completed': True},
                          format='json')
        self.assertEqual(Todo.objects.filter(column=self.col).count(),
                         before)

    def test_reopen_does_not_spawn(self):
        t = self._todo(recurrence='weekly', completed=True)
        before = Todo.objects.filter(column=self.col).count()
        self.client.patch(f'/api/todos/{t.id}/', {'completed': False},
                          format='json')
        self.assertEqual(Todo.objects.filter(column=self.col).count(),
                         before)

    def test_monthly_clamps_day(self):
        import datetime
        jan31 = self.tz.make_aware(datetime.datetime(2026, 1, 31, 9, 0))
        t = self._todo(recurrence='monthly', start=jan31)
        self.client.patch(f'/api/todos/{t.id}/', {'completed': True},
                          format='json')
        nxt = Todo.objects.filter(column=self.col,
                                  completed=False).latest('id')
        self.assertEqual(nxt.start_date.month, 2)
        self.assertEqual(nxt.start_date.day, 28)  # 2026 not a leap year


class BulkActionTests(ApiTestCase):
    def setUp(self):
        from .models import Label
        self.u = make_user('bku')
        self.outsider = make_user('bko')
        self.auth(self.u)
        self.d = DashBoard.objects.create(user=self.u, name='D')
        self.c1 = Column.objects.create(dashboard=self.d, name='c1')
        self.c2 = Column.objects.create(dashboard=self.d, name='c2')
        self.d2 = DashBoard.objects.create(user=self.u, name='D2')
        self.cx = Column.objects.create(dashboard=self.d2, name='cx')
        self.lbl = Label.objects.create(dashboard=self.d, name='L')
        self.lbl2 = Label.objects.create(dashboard=self.d2, name='L2')
        self.t1 = Todo.objects.create(column=self.c1, name='t1')
        self.t2 = Todo.objects.create(column=self.c1, name='t2')

    def _bulk(self, **body):
        return self.client.post('/api/todos/bulk/', body, format='json')

    def test_complete_and_reopen(self):
        r = self._bulk(ids=[self.t1.id, self.t2.id], action='complete')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['updated'], 2)
        self.t1.refresh_from_db()
        self.assertTrue(self.t1.completed)
        self._bulk(ids=[self.t1.id], action='reopen')
        self.t1.refresh_from_db()
        self.assertFalse(self.t1.completed)

    def test_complete_spawns_recurring(self):
        rt = Todo.objects.create(column=self.c1, name='rt',
                                 recurrence='daily')
        before = Todo.objects.filter(column=self.c1).count()
        self._bulk(ids=[rt.id], action='complete')
        self.assertEqual(Todo.objects.filter(column=self.c1).count(),
                         before + 1)

    def test_move_same_dashboard_ok_cross_blocked(self):
        ok = self._bulk(ids=[self.t1.id, self.t2.id], action='move',
                        value=self.c2.id)
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.t1.refresh_from_db()
        self.assertEqual(self.t1.column_id, self.c2.id)
        bad = self._bulk(ids=[self.t1.id], action='move',
                         value=self.cx.id)
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_label_add_same_dashboard_only(self):
        ok = self._bulk(ids=[self.t1.id], action='label_add',
                        value=self.lbl.id)
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertIn(self.lbl, self.t1.labels.all())
        bad = self._bulk(ids=[self.t1.id], action='label_add',
                         value=self.lbl2.id)
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_and_access_control(self):
        r = self._bulk(ids=[self.t2.id], action='delete')
        self.assertEqual(r.data, {'deleted': 1})
        self.assertFalse(Todo.objects.filter(id=self.t2.id).exists())
        # outsider can't touch our todos
        self.auth(self.outsider)
        r = self._bulk(ids=[self.t1.id], action='complete')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_bad_request(self):
        self.assertEqual(
            self._bulk(ids=[], action='complete').status_code,
            status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            self._bulk(ids=[self.t1.id], action='nope').status_code,
            status.HTTP_400_BAD_REQUEST)


class CalendarFeedTests(ApiTestCase):
    def setUp(self):
        self.u = make_user('calu')
        self.d = DashBoard.objects.create(user=self.u, name='D')
        self.col = Column.objects.create(dashboard=self.d, name='c')
        self.todo = Todo.objects.create(column=self.col,
                                        name='Plan, refine & ship')
        self.todo.users.add(self.u)

    def test_feed_token_and_regenerate(self):
        self.auth(self.u)
        r = self.client.get('/api/calendar/feed/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        tok1 = r.data['token']
        self.assertTrue(r.data['path'].endswith(f'{tok1}.ics'))
        r2 = self.client.post('/api/calendar/feed/')
        self.assertNotEqual(r2.data['token'], tok1)
        # old token no longer resolves
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(f'/api/calendar/{tok1}.ics').status_code, 404)

    def test_ics_public_and_escaped(self):
        self.auth(self.u)
        tok = self.client.get('/api/calendar/feed/').data['token']
        self.client.force_authenticate(user=None)  # no JWT
        r = self.client.get(f'/api/calendar/{tok}.ics')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertIn('text/calendar', r['Content-Type'])
        body = r.content.decode()
        self.assertIn('BEGIN:VCALENDAR', body)
        self.assertIn('BEGIN:VEVENT', body)
        self.assertIn(f'UID:todo-{self.todo.id}@dashboard', body)
        # comma in the name is escaped per RFC 5545
        self.assertIn('SUMMARY:Plan\\, refine & ship', body)

    def test_bad_token_404(self):
        self.assertEqual(
            self.client.get('/api/calendar/nope.ics').status_code, 404)


class WSTicketTests(ApiTestCase):
    def setUp(self):
        self.u = make_user('wsu')

    def test_endpoint_requires_auth(self):
        self.assertEqual(
            self.client.post('/api/ws-ticket/').status_code,
            status.HTTP_401_UNAUTHORIZED)

    def test_mint_and_single_use(self):
        from .ws_tickets import consume_ticket
        self.auth(self.u)
        r = self.client.post('/api/ws-ticket/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ticket = r.data['ticket']
        self.assertTrue(len(ticket) > 20)
        # First consume returns the user id, second returns None.
        self.assertEqual(consume_ticket(ticket), self.u.id)
        self.assertIsNone(consume_ticket(ticket))
        # Unknown ticket -> None.
        self.assertIsNone(consume_ticket('garbage'))
        self.assertIsNone(consume_ticket(''))


class NotificationCenterTests(ApiTestCase):
    def setUp(self):
        self.owner = make_user('ntowner')
        self.member = make_user('ntmember')
        self.d = DashBoard.objects.create(user=self.owner, name='D')
        self.d.users.add(self.member)
        self.col = Column.objects.create(dashboard=self.d, name='c')

    def test_assignment_creates_notification(self):
        self.auth(self.owner)
        self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 'task',
            'users': [self.member.id]}, format='json')
        # Member sees a notification; owner does not.
        self.auth(self.member)
        r = self.client.get('/api/notifications/')
        self.assertEqual(r.data['count'], 1)
        note = r.data['results'][0]
        self.assertEqual(note['kind'], 'todo_assigned')
        self.assertFalse(note['read'])
        self.assertIn(f'/dashboards/{self.d.id}/columns/{self.col.id}',
                      note['link'])
        self.auth(self.owner)
        self.assertEqual(
            self.client.get('/api/notifications/').data['count'], 0)

    def test_unread_count_and_mark_read(self):
        self.auth(self.owner)
        for i in range(3):
            self.client.post('/api/todos/', {
                'column': self.col.id, 'name': f't{i}',
                'users': [self.member.id]}, format='json')
        self.auth(self.member)
        self.assertEqual(
            self.client.get('/api/notifications/unread_count/')
            .data['count'], 3)
        first = self.client.get('/api/notifications/').data['results'][0]
        self.client.post(f'/api/notifications/{first["id"]}/read/')
        self.assertEqual(
            self.client.get('/api/notifications/unread_count/')
            .data['count'], 2)
        self.client.post('/api/notifications/read_all/')
        self.assertEqual(
            self.client.get('/api/notifications/unread_count/')
            .data['count'], 0)


class DependencyTests(ApiTestCase):
    def setUp(self):
        self.u = make_user('depu')
        self.auth(self.u)
        self.d = DashBoard.objects.create(user=self.u, name='D')
        self.col = Column.objects.create(dashboard=self.d, name='c')
        self.d2 = DashBoard.objects.create(user=self.u, name='D2')
        self.col2 = Column.objects.create(dashboard=self.d2, name='c2')
        self.a = Todo.objects.create(column=self.col, name='A')
        self.b = Todo.objects.create(column=self.col, name='B')
        self.foreign = Todo.objects.create(column=self.col2, name='F')

    def test_block_completion_until_blocker_done(self):
        r = self.client.patch(f'/api/todos/{self.b.id}/',
                              {'blockers': [self.a.id]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['blockers_open'], 1)
        # B can't complete while A is open.
        r = self.client.patch(f'/api/todos/{self.b.id}/',
                              {'completed': True}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('completed', r.data)
        # Complete A, then B is allowed.
        self.client.patch(f'/api/todos/{self.a.id}/',
                          {'completed': True}, format='json')
        r = self.client.patch(f'/api/todos/{self.b.id}/',
                              {'completed': True}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['blockers_open'], 0)

    def test_no_self_block(self):
        r = self.client.patch(f'/api/todos/{self.a.id}/',
                              {'blockers': [self.a.id]}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('blockers', r.data)

    def test_cross_dashboard_blocker_rejected(self):
        r = self.client.patch(f'/api/todos/{self.b.id}/',
                              {'blockers': [self.foreign.id]},
                              format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('blockers', r.data)


class WebhookTests(ApiTestCase):
    def setUp(self):
        self.owner = make_user('whowner')
        self.member = make_user('whmember')
        self.d = DashBoard.objects.create(user=self.owner, name='D')
        self.d.users.add(self.member)
        self.col = Column.objects.create(dashboard=self.d, name='c')

    def test_only_owner_manages(self):
        self.auth(self.member)
        r = self.client.post('/api/webhooks/', {
            'dashboard': self.d.id, 'url': 'http://x.test/hook',
            'events': []}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.auth(self.owner)
        r = self.client.post('/api/webhooks/', {
            'dashboard': self.d.id, 'url': 'http://x.test/hook',
            'events': ['created']}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.get('/api/webhooks/').data['count'], 1)
        self.auth(self.member)
        self.assertEqual(self.client.get('/api/webhooks/').data['count'], 0)

    def test_bad_event_rejected(self):
        self.auth(self.owner)
        r = self.client.post('/api/webhooks/', {
            'dashboard': self.d.id, 'url': 'http://x.test/h',
            'events': ['nope']}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('dashboard.serializers._deliver_webhook')
    def test_fires_on_matching_event_only(self, deliver):
        self.auth(self.owner)
        self.client.post('/api/webhooks/', {
            'dashboard': self.d.id, 'url': 'http://x.test/h',
            'events': ['created'], 'active': True}, format='json')
        r = self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 't'}, format='json')
        self.assertTrue(deliver.called)
        args = deliver.call_args[0]
        self.assertEqual(args[0], 'http://x.test/h')
        self.assertEqual(args[1]['event'], 'created')
        deliver.reset_mock()
        self.client.patch(f"/api/todos/{r.data['id']}/",
                          {'completed': True}, format='json')
        self.assertFalse(deliver.called)

    @patch('dashboard.serializers._deliver_webhook')
    def test_inactive_not_fired(self, deliver):
        self.auth(self.owner)
        self.client.post('/api/webhooks/', {
            'dashboard': self.d.id, 'url': 'http://x.test/h',
            'events': [], 'active': False}, format='json')
        self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 't'}, format='json')
        self.assertFalse(deliver.called)


class EmailNotificationTests(ApiTestCase):
    def setUp(self):
        self.owner = make_user('emowner')
        self.member = make_user('emmember')
        self.member.email = 'member@example.com'
        self.member.save(update_fields=['email'])
        self.d = DashBoard.objects.create(user=self.owner, name='D')
        self.d.users.add(self.member)
        self.col = Column.objects.create(dashboard=self.d, name='c')

    def test_email_on_assignment_default_on(self):
        mail.outbox = []
        self.auth(self.owner)
        self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 'task',
            'users': [self.member.id]}, format='json')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['member@example.com'])

    def test_opt_out_suppresses_email(self):
        self.auth(self.member)
        r = self.client.patch('/api/auth/preferences/',
                              {'email_on_assign': False}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data['email_on_assign'])
        mail.outbox = []
        self.auth(self.owner)
        self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 'task2',
            'users': [self.member.id]}, format='json')
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_without_address(self):
        no_addr = make_user('emnoaddr')
        self.d.users.add(no_addr)
        mail.outbox = []
        self.auth(self.owner)
        self.client.post('/api/todos/', {
            'column': self.col.id, 'name': 't3',
            'users': [no_addr.id]}, format='json')
        self.assertEqual(len(mail.outbox), 0)

    def test_email_on_mention(self):
        mail.outbox = []
        self.auth(self.owner)
        t = Todo.objects.create(column=self.col, name='mt')
        self.client.post('/api/comments/', {
            'todo': t.id, 'body': 'ping @emmember'}, format='json')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('mt', mail.outbox[0].subject)

    def test_preferences_get_defaults(self):
        self.auth(self.member)
        r = self.client.get('/api/auth/preferences/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(
            r.data, {'email_on_assign': True, 'email_on_mention': True})
