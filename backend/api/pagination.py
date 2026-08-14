from math import ceil

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class MobilePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

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
