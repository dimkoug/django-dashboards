from django.urls import reverse_lazy
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect

from .models import Column, Dashboard, Document



def get_dashboard_for_sb(request):
    """"
    Return Data for  select box 2  plugin
    """
    results = []
    if not request.user.is_authenticated:
        return JsonResponse(results, safe=False)
    search = request.GET.get('search')
    if search and search != '':
        data = Dashboard.objects.prefetch_related('profiles').filter(
            Q(name__icontains=search),profiles=request.user.profile
        ).values('id', 'name')
        for d in data:
            results.append({'id':d['id'], "text": d['name']})
        # j_data = serializers.serialize("json", data, fields=('erp_code', 'title'))
        # return JsonResponse(j_data, safe=False)
    return JsonResponse({"results": results}, safe=False)


def get_column_for_sb(request):
    """"
    Return Data for  select box 2  plugin
    """
    results = []
    if not request.user.is_authenticated:
        return JsonResponse(results, safe=False)
    search = request.GET.get('search')
    if search and search != '':
        data = Column.objects.select_related('dashboard').prefetch_related('dashboard__profiles').filter(
            Q(name__icontains=search),dashboard__profiles=request.user.profile
        ).values('id', 'name')
        for d in data:
            results.append({'id':d['id'], "text": d['name']})
        # j_data = serializers.serialize("json", data, fields=('erp_code', 'title'))
        # return JsonResponse(j_data, safe=False)
    return JsonResponse({"results": results}, safe=False)


def delete_document(request,pk):
    document = Document.objects.select_related('task__column__dashboard').prefetch_related('task__column__dashboard__profiles').get(id=pk,task__column__dashboard__profiles=request.user.profile)
    task = document.task
    document.delete()
    return redirect(reverse_lazy("dashboards:task-detail",kwargs={"pk":task.id}))