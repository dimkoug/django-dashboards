from rest_framework.permissions import SAFE_METHODS, BasePermission


class DashBoardPermission(BasePermission):
    """Owner or shared member may view a dashboard; only the owner may
    modify it, delete it, or change its membership (sharing)."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return (obj.user_id == request.user.id
                    or obj.users.filter(id=request.user.id).exists())
        return obj.user_id == request.user.id


class CommentPermission(BasePermission):
    """Anyone with dashboard access may read/add (queryset-scoped);
    only the comment's author or the dashboard owner may delete it."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return (obj.author_id == request.user.id
                or obj.todo.column.dashboard.user_id == request.user.id)


class AttachmentPermission(BasePermission):
    """Members read/upload (queryset-scoped); only the uploader or the
    dashboard owner may delete an attachment."""

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return (obj.uploaded_by_id == request.user.id
                or obj.todo.column.dashboard.user_id == request.user.id)
