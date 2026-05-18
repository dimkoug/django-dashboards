import django_filters

from .models import Todo


class TodoFilter(django_filters.FilterSet):
    """?completed= ?assignee=<id> ?priority=low|medium|high ?label=<id>
    (plus ?search= / ?ordering=)."""

    completed = django_filters.BooleanFilter()
    assignee = django_filters.NumberFilter(
        field_name='users', distinct=True,
        help_text='User id the todo is assigned to.')
    priority = django_filters.ChoiceFilter(choices=Todo.Priority.choices)
    label = django_filters.NumberFilter(
        field_name='labels', distinct=True,
        help_text='Label id applied to the todo.')

    class Meta:
        model = Todo
        fields = ['completed', 'assignee', 'priority', 'label']
