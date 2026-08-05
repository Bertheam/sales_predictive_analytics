from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView

from companies.models import Company, Membership
from dashboard.data import get_dashboard_snapshot
from operations.data import product_catalog, sales_overview, stock_overview
from .serializers import MembershipSerializer


def require_company(request):
    company = getattr(request, "company", None)
    if company:
        return company, None
    return None, Response(
        {"detail": "Sélectionnez d'abord un dépôt actif."},
        status=status.HTTP_409_CONFLICT,
    )


class MeView(APIView):
    def get(self, request):
        return Response({
            "id": request.user.id,
            "email": request.user.email,
            "full_name": request.user.full_name,
        })


class CompanyListView(APIView):
    def get(self, request):
        memberships = Membership.objects.select_related("company").filter(
            user=request.user,
            status=Membership.Status.ACTIVE,
            company__status=Company.Status.ACTIVE,
        )
        return Response(MembershipSerializer(memberships, many=True).data)


class ContextView(APIView):
    def get(self, request):
        company = getattr(request, "company", None)
        membership = getattr(request, "membership", None)
        return Response({
            "user": {
                "id": request.user.id,
                "email": request.user.email,
                "full_name": request.user.full_name,
            },
            "company": None if not company else {
                "id": company.id,
                "code": company.code,
                "name": company.name,
                "currency": company.currency,
                "timezone": company.timezone,
            },
            "role": None if not membership else membership.role,
        })


class DashboardSummaryView(APIView):
    def get(self, request):
        company, error = require_company(request)
        if error:
            return error
        snapshot = get_dashboard_snapshot(company.id)
        return Response({
            "company_id": str(company.id),
            "ready": snapshot.ready,
            "period": {
                "start": snapshot.min_date,
                "end": snapshot.max_date,
            },
            "revenue": snapshot.revenue,
            "sales_count": snapshot.sales_count,
            "quantity_sold": snapshot.quantity_sold,
            "current_stock": snapshot.current_stock,
            "risk_products": snapshot.risk_products,
            "active_products": snapshot.active_products,
        })


class ProductListView(APIView):
    def get(self, request):
        company, error = require_company(request)
        if error:
            return error
        state = request.query_params.get("status", "active")
        if state not in {"all", "active", "inactive"}:
            state = "active"
        rows, summary = product_catalog(
            company.id,
            query=request.query_params.get("q", "").strip()[:100],
            status=state,
        )
        return Response({"company_id": str(company.id), "summary": summary, "results": rows})


class StockListView(APIView):
    def get(self, request):
        company, error = require_company(request)
        if error:
            return error
        stock_status = request.query_params.get("status", "all")
        if stock_status not in {"all", "OK", "LOW", "OUT", "UNTRACKED"}:
            stock_status = "all"
        rows, summary = stock_overview(
            company.id,
            query=request.query_params.get("q", "").strip()[:100],
            stock_status=stock_status,
        )
        return Response({"company_id": str(company.id), "summary": summary, "results": rows})


class SaleListView(APIView):
    def get(self, request):
        company, error = require_company(request)
        if error:
            return error
        rows, summary, start_date, end_date = sales_overview(
            company.id,
            query=request.query_params.get("q", "").strip()[:100],
        )
        return Response({
            "company_id": str(company.id),
            "period": {"start": start_date, "end": end_date},
            "summary": summary,
            "results": rows,
        })
