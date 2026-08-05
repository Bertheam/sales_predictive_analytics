from datetime import date, time
from uuid import UUID

from django.contrib import messages
from django.db import IntegrityError
from django.http import Http404
from django.shortcuts import redirect, render

from companies.models import Membership
from companies.permissions import company_required, company_roles_required
from .data import (
    customer_catalog,
    get_product,
    get_customer,
    get_supplier,
    create_manual_movement,
    create_receipt,
    create_sale,
    cancel_sale,
    cancel_receipt,
    inventory_history,
    list_categories,
    list_customer_types,
    product_catalog,
    operational_references,
    receipt_detail,
    sale_detail,
    sales_overview,
    save_product,
    save_customer,
    save_supplier,
    set_customer_archived,
    set_product_archived,
    set_supplier_archived,
    stock_overview,
    update_sale_metadata,
    update_receipt_metadata,
    supplier_catalog,
)
from .forms import CustomerForm, MovementForm, ProductForm, ReceiptEditForm, ReceiptForm, ReceiptItemFormSet, SaleEditForm, SaleForm, SaleItemFormSet, SupplierForm
from .listing import sort_and_paginate
from audit.models import AuditLog
from audit.services import record_audit


MANAGEMENT_ROLES = (
    Membership.Role.OWNER,
    Membership.Role.ADMIN,
)


def _parse_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _parse_uuid(value):
    try:
        return str(UUID(value)) if value else ""
    except (TypeError, ValueError):
        return ""


@company_required
def products(request):
    query = request.GET.get("q", "").strip()[:100]
    category_id = _parse_uuid(request.GET.get("category", "").strip())
    status = request.GET.get("status", "active")
    if status not in {"all", "active", "inactive", "archived"}:
        status = "active"
    rows, summary = product_catalog(
        request.company.id,
        query=query,
        category_id=category_id,
        status=status,
    )
    page_obj, sort_state, pagination_state = sort_and_paginate(
        request, rows,
        allowed_sorts={
            "product": "name", "category": "category_name",
            "package": "units_per_package", "stock": "closing_stock",
            "price": "selling_price",
            "status": lambda row: (row["deleted_at"] is not None, not row["is_active"]),
        },
        default_sort="product",
    )
    return render(request, "operations/products.html", {
        "products": page_obj.object_list,
        "page_obj": page_obj, "sort_state": sort_state,
        "pagination_state": pagination_state,
        "summary": summary,
        "categories": list_categories(request.company.id),
        "filters": {"q": query, "category": category_id, "status": status},
        "can_manage": request.membership.role in MANAGEMENT_ROLES,
    })


@company_roles_required(*MANAGEMENT_ROLES)
def product_create(request):
    categories = list_categories(request.company.id)
    form = ProductForm(request.POST or None, categories=categories)
    if request.method == "POST" and form.is_valid():
        try:
            result = save_product(request.company.id, form.cleaned_data, user_id=request.user.id)
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else "Ce produit existe déjà dans ce dépôt.")
        else:
            record_audit(
                request,
                action=AuditLog.Action.CREATE,
                resource_type="product",
                resource_id=result["id"],
                description=f"Création du produit {result['code']} · {form.cleaned_data['name']}.",
                metadata={"product_code": result["code"]},
            )
            messages.success(request, f"Produit {result['code']} créé avec succès.")
            return redirect("operations:products")
    return render(request, "operations/product_form.html", {
        "form": form,
        "page_title": "Ajouter un produit",
        "submit_label": "Créer le produit",
    })


@company_roles_required(*MANAGEMENT_ROLES)
def product_edit(request, product_id):
    product = get_product(request.company.id, product_id)
    if not product:
        raise Http404("Produit introuvable dans ce dépôt.")
    categories = list_categories(request.company.id)
    form = ProductForm(request.POST or None, categories=categories, initial=product)
    if request.method == "POST" and form.is_valid():
        try:
            result = save_product(
                request.company.id, form.cleaned_data, product_id, user_id=request.user.id
            )
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else "Un produit identique existe déjà dans ce dépôt.")
        else:
            record_audit(
                request,
                action=AuditLog.Action.UPDATE,
                resource_type="product",
                resource_id=result["id"],
                description=f"Modification du produit {result['code']} · {form.cleaned_data['name']}.",
                metadata={"product_code": result["code"]},
            )
            messages.success(request, f"Produit {result['code']} mis à jour.")
            return redirect("operations:products")
    return render(request, "operations/product_form.html", {
        "form": form,
        "page_title": f"Modifier {product['name']}",
        "submit_label": "Enregistrer les modifications",
        "product": product,
    })


@company_roles_required(*MANAGEMENT_ROLES)
def product_archive(request, product_id):
    if request.method != "POST":
        raise Http404
    archived = request.POST.get("action") != "restore"
    product = set_product_archived(
        request.company.id,
        product_id,
        archived=archived,
        user_id=request.user.id,
    )
    if not product:
        raise Http404("Produit introuvable dans ce dépôt.")
    record_audit(
        request,
        action=AuditLog.Action.DELETE if archived else AuditLog.Action.UPDATE,
        resource_type="product",
        resource_id=product["id"],
        description=(
            f"Archivage du produit {product['code']} · {product['name']}."
            if archived
            else f"Restauration du produit {product['code']} · {product['name']}."
        ),
        metadata={"logical_deletion": archived, "product_code": product["code"]},
    )
    messages.success(
        request,
        "Produit archivé sans supprimer son historique."
        if archived else "Produit restauré et réactivé.",
    )
    return redirect("operations:products")


@company_required
def customers(request):
    query = request.GET.get("q", "").strip()[:100]
    customer_type_id = _parse_uuid(request.GET.get("type", "").strip())
    status = request.GET.get("status", "active")
    if status not in {"all", "active", "inactive", "archived"}:
        status = "active"
    rows, summary = customer_catalog(
        request.company.id,
        query=query,
        customer_type_id=customer_type_id,
        status=status,
    )
    page_obj, sort_state, pagination_state = sort_and_paginate(
        request, rows,
        allowed_sorts={
            "customer": "name", "type": "type_name",
            "location": lambda row: row.get("zone") or row.get("district") or row.get("city"),
            "phone": "phone", "sales": "sale_count", "revenue": "revenue",
            "status": lambda row: (row["deleted_at"] is not None, not row["is_active"]),
        },
        default_sort="customer",
    )
    return render(request, "operations/customers.html", {
        "customers": page_obj.object_list,
        "page_obj": page_obj, "sort_state": sort_state,
        "pagination_state": pagination_state,
        "summary": summary,
        "customer_types": list_customer_types(request.company.id),
        "filters": {"q": query, "type": customer_type_id, "status": status},
        "can_manage": request.membership.role in MANAGEMENT_ROLES,
    })


@company_roles_required(*MANAGEMENT_ROLES)
def customer_create(request):
    customer_types = list_customer_types(request.company.id)
    form = CustomerForm(request.POST or None, customer_types=customer_types)
    if request.method == "POST" and form.is_valid():
        try:
            result = save_customer(
                request.company.id, form.cleaned_data, user_id=request.user.id
            )
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else "Ce numéro de téléphone est déjà utilisé dans ce dépôt.")
        else:
            record_audit(request, action=AuditLog.Action.CREATE, resource_type="customer", resource_id=result["id"], description=f"Création du client {result['code']} · {result['name']}.", metadata={"customer_code": result["code"]})
            messages.success(request, f"Client {result['code']} créé avec succès.")
            return redirect("operations:customers")
    return render(request, "operations/customer_form.html", {
        "form": form, "page_title": "Ajouter un client",
        "submit_label": "Créer le client",
    })


@company_roles_required(*MANAGEMENT_ROLES)
def customer_edit(request, customer_id):
    customer = get_customer(request.company.id, customer_id)
    if not customer:
        raise Http404("Client introuvable dans ce dépôt.")
    form = CustomerForm(
        request.POST or None,
        customer_types=list_customer_types(request.company.id),
        initial=customer,
    )
    if request.method == "POST" and form.is_valid():
        try:
            result = save_customer(
                request.company.id, form.cleaned_data, customer_id,
                user_id=request.user.id,
            )
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else "Ce numéro de téléphone est déjà utilisé dans ce dépôt.")
        else:
            record_audit(request, action=AuditLog.Action.UPDATE, resource_type="customer", resource_id=result["id"], description=f"Modification du client {result['code']} · {result['name']}.", metadata={"customer_code": result["code"]})
            messages.success(request, f"Client {result['code']} mis à jour.")
            return redirect("operations:customers")
    return render(request, "operations/customer_form.html", {
        "form": form, "page_title": f"Modifier {customer['name']}",
        "submit_label": "Enregistrer les modifications", "customer": customer,
    })


@company_roles_required(*MANAGEMENT_ROLES)
def customer_archive(request, customer_id):
    if request.method != "POST":
        raise Http404
    archived = request.POST.get("action") != "restore"
    try:
        customer = set_customer_archived(
            request.company.id, customer_id, archived=archived,
            user_id=request.user.id,
        )
    except IntegrityError:
        messages.error(request, "Ce client ne peut pas être restauré car son téléphone est déjà utilisé.")
        return redirect("operations:customers")
    if not customer:
        raise Http404("Client introuvable dans ce dépôt.")
    record_audit(request, action=AuditLog.Action.DELETE if archived else AuditLog.Action.UPDATE, resource_type="customer", resource_id=customer["id"], description=(f"Archivage du client {customer['code']} · {customer['name']}." if archived else f"Restauration du client {customer['code']} · {customer['name']}."), metadata={"logical_deletion": archived, "customer_code": customer["code"]})
    messages.success(request, "Client archivé sans supprimer ses ventes." if archived else "Client restauré et réactivé.")
    return redirect("operations:customers")


@company_required
def suppliers(request):
    query = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "active")
    if status not in {"all", "active", "inactive", "archived"}:
        status = "active"
    rows, summary = supplier_catalog(
        request.company.id, query=query, status=status
    )
    page_obj, sort_state, pagination_state = sort_and_paginate(
        request, rows,
        allowed_sorts={
            "supplier": "name", "city": "city", "phone": "phone",
            "receipts": "receipt_count", "amount": "purchased_amount",
            "status": lambda row: (row["deleted_at"] is not None, not row["is_active"]),
        },
        default_sort="supplier",
    )
    return render(request, "operations/suppliers.html", {
        "suppliers": page_obj.object_list, "summary": summary,
        "page_obj": page_obj, "sort_state": sort_state,
        "pagination_state": pagination_state,
        "filters": {"q": query, "status": status},
        "can_manage": request.membership.role in MANAGEMENT_ROLES,
    })


@company_roles_required(*MANAGEMENT_ROLES)
def supplier_create(request):
    form = SupplierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            result = save_supplier(
                request.company.id, form.cleaned_data, user_id=request.user.id
            )
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else "Un fournisseur portant ce nom existe déjà dans ce dépôt.")
        else:
            record_audit(request, action=AuditLog.Action.CREATE, resource_type="supplier", resource_id=result["id"], description=f"Création du fournisseur {result['code']} · {result['name']}.", metadata={"supplier_code": result["code"]})
            messages.success(request, f"Fournisseur {result['code']} créé avec succès.")
            return redirect("operations:suppliers")
    return render(request, "operations/supplier_form.html", {
        "form": form, "page_title": "Ajouter un fournisseur",
        "submit_label": "Créer le fournisseur",
    })


@company_roles_required(*MANAGEMENT_ROLES)
def supplier_edit(request, supplier_id):
    supplier = get_supplier(request.company.id, supplier_id)
    if not supplier:
        raise Http404("Fournisseur introuvable dans ce dépôt.")
    form = SupplierForm(request.POST or None, initial=supplier)
    if request.method == "POST" and form.is_valid():
        try:
            result = save_supplier(
                request.company.id, form.cleaned_data, supplier_id,
                user_id=request.user.id,
            )
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else "Un fournisseur portant ce nom existe déjà dans ce dépôt.")
        else:
            record_audit(request, action=AuditLog.Action.UPDATE, resource_type="supplier", resource_id=result["id"], description=f"Modification du fournisseur {result['code']} · {result['name']}.", metadata={"supplier_code": result["code"]})
            messages.success(request, f"Fournisseur {result['code']} mis à jour.")
            return redirect("operations:suppliers")
    return render(request, "operations/supplier_form.html", {
        "form": form, "page_title": f"Modifier {supplier['name']}",
        "submit_label": "Enregistrer les modifications", "supplier": supplier,
    })


@company_roles_required(*MANAGEMENT_ROLES)
def supplier_archive(request, supplier_id):
    if request.method != "POST":
        raise Http404
    archived = request.POST.get("action") != "restore"
    try:
        supplier = set_supplier_archived(
            request.company.id, supplier_id, archived=archived,
            user_id=request.user.id,
        )
    except IntegrityError:
        messages.error(request, "Ce fournisseur ne peut pas être restauré car son nom est déjà utilisé.")
        return redirect("operations:suppliers")
    if not supplier:
        raise Http404("Fournisseur introuvable dans ce dépôt.")
    record_audit(request, action=AuditLog.Action.DELETE if archived else AuditLog.Action.UPDATE, resource_type="supplier", resource_id=supplier["id"], description=(f"Archivage du fournisseur {supplier['code']} · {supplier['name']}." if archived else f"Restauration du fournisseur {supplier['code']} · {supplier['name']}."), metadata={"logical_deletion": archived, "supplier_code": supplier["code"]})
    messages.success(request, "Fournisseur archivé sans supprimer ses réceptions." if archived else "Fournisseur restauré et réactivé.")
    return redirect("operations:suppliers")


@company_required
def stocks(request):
    query = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "all")
    if status not in {"all", "OK", "LOW", "OUT", "UNTRACKED"}:
        status = "all"
    rows, summary = stock_overview(request.company.id, query=query, stock_status=status)
    receipts, movements = inventory_history(request.company.id)
    stock_page, stock_sort, stock_pagination = sort_and_paginate(
        request, rows,
        allowed_sorts={
            "product": "name", "stock": "closing_stock", "minimum": "minimum_stock",
            "reorder": "reorder_quantity", "date": "stock_date", "level": "stock_status",
        }, default_sort="product", prefix="stock_",
    )
    receipt_page, receipt_sort, receipt_pagination = sort_and_paginate(
        request, receipts,
        allowed_sorts={
            "receipt": "receipt_number", "date": "receipt_date",
            "supplier": "supplier_name", "products": "item_count",
            "quantity": "quantity", "amount": "total_amount",
        }, default_sort="date", default_direction="desc", per_page=10,
        prefix="receipt_",
    )
    movement_page, movement_sort, movement_pagination = sort_and_paginate(
        request, movements,
        allowed_sorts={
            "movement": "movement_number", "date": "movement_date",
            "product": "product_name", "type": "movement_label",
            "direction": "direction", "quantity": "quantity_packages", "reason": "reason",
        }, default_sort="date", default_direction="desc", per_page=10,
        prefix="movement_",
    )
    return render(request, "operations/stocks.html", {
        "stocks": stock_page.object_list,
        "receipts": receipt_page.object_list,
        "movements": movement_page.object_list,
        "stock_page": stock_page, "stock_sort": stock_sort,
        "stock_pagination": stock_pagination,
        "receipt_page": receipt_page, "receipt_sort": receipt_sort,
        "receipt_pagination": receipt_pagination,
        "movement_page": movement_page, "movement_sort": movement_sort,
        "movement_pagination": movement_pagination,
        "summary": summary,
        "filters": {"q": query, "status": status},
        "can_manage": request.membership.role in MANAGEMENT_ROLES,
    })


@company_required
def sales(request):
    query = request.GET.get("q", "").strip()[:100]
    requested_start = _parse_date(request.GET.get("start"))
    requested_end = _parse_date(request.GET.get("end"))
    if requested_start and requested_end and requested_start > requested_end:
        messages.error(request, "La date de début doit précéder la date de fin.")
        requested_start = requested_end
    rows, summary, start_date, end_date = sales_overview(
        request.company.id,
        start_date=requested_start,
        end_date=requested_end,
        query=query,
    )
    page_obj, sort_state, pagination_state = sort_and_paginate(
        request, rows,
        allowed_sorts={
            "sale": "sale_number",
            "date": lambda row: (row["sale_date"], row.get("sale_time") or time.min),
            "customer": "customer_name", "items": "item_count",
            "quantity": "quantity", "payment": "payment_status",
            "amount": "total_amount",
        },
        default_sort="date", default_direction="desc",
    )
    return render(request, "operations/sales.html", {
        "sales": page_obj.object_list,
        "page_obj": page_obj, "sort_state": sort_state,
        "pagination_state": pagination_state,
        "summary": summary,
        "filters": {"q": query, "start": start_date, "end": end_date},
        "can_manage": request.membership.role in MANAGEMENT_ROLES,
    })


@company_required
def sale_show(request, sale_id):
    sale, items = sale_detail(request.company.id, sale_id)
    if not sale:
        raise Http404("Vente introuvable dans ce dépôt.")
    return render(request, "operations/sale_detail.html", {"sale": sale, "items": items, "can_manage": request.membership.role in MANAGEMENT_ROLES})


@company_roles_required(*MANAGEMENT_ROLES)
def sale_edit(request, sale_id):
    sale, _ = sale_detail(request.company.id, sale_id)
    if not sale:
        raise Http404("Vente introuvable dans ce dépôt.")
    references = operational_references(request.company.id)
    form = SaleEditForm(request.POST or None, customers=references["customers"], initial=sale)
    if request.method == "POST" and form.is_valid():
        result = update_sale_metadata(request.company.id, sale_id, request.user.id, form.cleaned_data)
        if not result:
            raise Http404("Vente introuvable dans ce dépôt.")
        record_audit(request, action=AuditLog.Action.UPDATE, resource_type="sale", resource_id=result["id"], description=f"Modification des informations commerciales de la vente {result['number']}.")
        messages.success(request, f"Vente {result['number']} mise à jour.")
        return redirect("operations:sale-detail", sale_id=sale_id)
    return render(request, "operations/sale_edit.html", {"form": form, "sale": sale})


@company_roles_required(*MANAGEMENT_ROLES)
def sale_cancel(request, sale_id):
    if request.method != "POST":
        raise Http404
    result = cancel_sale(request.company.id, sale_id, request.user.id)
    if not result:
        raise Http404("Vente introuvable dans ce dépôt.")
    record_audit(request, action=AuditLog.Action.DELETE, resource_type="sale", resource_id=result["id"], description=f"Annulation logique de la vente {result['number']} et retour des quantités en stock.", metadata={"logical_deletion": True, "returned_lines": result["returned_lines"]})
    messages.success(request, f"Vente {result['number']} annulée. Les quantités ont été retournées au stock.")
    return redirect("operations:sales")


@company_roles_required(*MANAGEMENT_ROLES)
def sale_create(request):
    references = operational_references(request.company.id)
    form = SaleForm(request.POST or None, customers=references["customers"])
    items = SaleItemFormSet(
        request.POST or None,
        prefix="items",
        form_kwargs={"products": references["products"]},
    )
    if request.method == "POST" and form.is_valid() and items.is_valid():
        try:
            result = create_sale(
                request.company.id,
                request.user.id,
                form.cleaned_data,
                [item.cleaned_data for item in items],
                request.user.full_name or request.user.email,
            )
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else "La vente n’a pas pu être enregistrée.")
        else:
            record_audit(request, action=AuditLog.Action.CREATE, resource_type="sale", resource_id=result["id"], description=f"Création de la vente {result['number']}.", metadata={"sale_number": result["number"], "total": str(result["total"])})
            messages.success(request, f"Vente {result['number']} enregistrée avec succès.")
            return redirect("operations:sale-detail", sale_id=result["id"])
    return render(request, "operations/sale_form.html", {"form": form, "items": items})


@company_roles_required(*MANAGEMENT_ROLES)
def receipt_create(request):
    references = operational_references(request.company.id)
    form = ReceiptForm(request.POST or None, suppliers=references["suppliers"])
    items = ReceiptItemFormSet(
        request.POST or None,
        prefix="items",
        form_kwargs={"products": references["products"]},
    )
    if request.method == "POST" and form.is_valid() and items.is_valid():
        try:
            result = create_receipt(
                request.company.id,
                request.user.id,
                form.cleaned_data,
                [item.cleaned_data for item in items],
            )
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else "La réception n’a pas pu être enregistrée.")
        else:
            record_audit(request, action=AuditLog.Action.CREATE, resource_type="purchase_receipt", resource_id=result["id"], description=f"Création de la réception {result['number']}.", metadata={"receipt_number": result["number"], "total": str(result["total"])})
            messages.success(request, f"Réception {result['number']} enregistrée et stock mis à jour.")
            return redirect("operations:stocks")
    return render(request, "operations/receipt_form.html", {"form": form, "items": items})


@company_roles_required(*MANAGEMENT_ROLES)
def receipt_edit(request, receipt_id):
    receipt = receipt_detail(request.company.id, receipt_id)
    if not receipt:
        raise Http404("Réception introuvable dans ce dépôt.")
    references = operational_references(request.company.id)
    form = ReceiptEditForm(
        request.POST or None,
        suppliers=references["suppliers"],
        initial=receipt,
    )
    if request.method == "POST" and form.is_valid():
        try:
            result = update_receipt_metadata(
                request.company.id, receipt_id, request.user.id, form.cleaned_data
            )
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else "La réception n’a pas pu être modifiée.")
        else:
            if not result:
                raise Http404("Réception introuvable dans ce dépôt.")
            record_audit(request, action=AuditLog.Action.UPDATE, resource_type="purchase_receipt", resource_id=result["id"], description=f"Modification du fournisseur de la réception {result['number']}.")
            messages.success(request, f"Réception {result['number']} mise à jour.")
            return redirect("operations:stocks")
    return render(request, "operations/receipt_edit.html", {"form": form, "receipt": receipt})


@company_roles_required(*MANAGEMENT_ROLES)
def receipt_cancel(request, receipt_id):
    if request.method != "POST":
        raise Http404
    try:
        result = cancel_receipt(request.company.id, receipt_id, request.user.id)
    except (IntegrityError, ValueError) as exc:
        messages.error(request, str(exc) if isinstance(exc, ValueError) else "La réception n’a pas pu être annulée.")
        return redirect("operations:stocks")
    if not result:
        raise Http404("Réception introuvable dans ce dépôt.")
    record_audit(request, action=AuditLog.Action.DELETE, resource_type="purchase_receipt", resource_id=result["id"], description=f"Annulation logique de la réception {result['number']} et sortie compensatoire du stock.", metadata={"logical_deletion": True, "returned_lines": result["returned_lines"]})
    messages.success(request, f"Réception {result['number']} annulée. Les quantités ont été retirées du stock.")
    return redirect("operations:stocks")


@company_roles_required(*MANAGEMENT_ROLES)
def movement_create(request):
    references = operational_references(request.company.id)
    form = MovementForm(request.POST or None, products=references["products"])
    if request.method == "POST" and form.is_valid():
        try:
            result = create_manual_movement(request.company.id, request.user.id, form.cleaned_data)
        except (IntegrityError, ValueError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else "Le mouvement n’a pas pu être enregistré.")
        else:
            record_audit(request, action=AuditLog.Action.CREATE, resource_type="stock_movement", resource_id=result["id"], description=f"Création du mouvement {result['number']} pour {result['product']}.", metadata={"movement_number": result["number"], "previous_stock": str(result["previous"]), "current_stock": str(result["current"])})
            messages.success(request, f"Mouvement {result['number']} enregistré. Nouveau stock : {result['current']} colis.")
            return redirect("operations:stocks")
    return render(request, "operations/movement_form.html", {"form": form})
