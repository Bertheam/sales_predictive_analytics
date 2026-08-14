from math import ceil

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param


class MobilePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    @classmethod
    def database_page(cls, request):
        paginator = cls()
        try:
            page = max(int(request.query_params.get(paginator.page_query_param, 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(request.query_params.get(paginator.page_size_query_param, paginator.page_size))
        except (TypeError, ValueError):
            page_size = paginator.page_size
        page_size = min(max(page_size, 1), paginator.max_page_size)
        return page, page_size, (page - 1) * page_size

    @classmethod
    def database_response(cls, request, rows, count, *, company_id=None):
        page, page_size, _ = cls.database_page(request)
        pages = ceil(count / page_size) if count else 0
        base_url = request.build_absolute_uri()
        next_url = replace_query_param(base_url, "page", page + 1) if page < pages else None
        previous_url = replace_query_param(base_url, "page", page - 1) if page > 1 and pages else None
        data = {
            "results": rows,
            "pagination": {
                "page": page, "page_size": page_size, "count": count,
                "pages": pages, "next": next_url, "previous": previous_url,
            },
        }
        if company_id is not None:
            data["company_id"] = str(company_id)
        return Response(data)

    def get_paginated_response(self, data):
        count = self.page.paginator.count
        return Response({
            "results": data,
            "pagination": {
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "count": count,
                "pages": ceil(count / self.get_page_size(self.request)) if count else 0,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
            },
        })
