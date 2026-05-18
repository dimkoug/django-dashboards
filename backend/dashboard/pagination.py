from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Paginated list responses: {count, next, previous, results}.

    Clients may request a larger page with ?page_size= (capped).
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000
