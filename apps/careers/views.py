"""
careers/views.py — Template views for career catalog
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404

from apps.careers.models import CareerSector, CareerPath


@login_required
def sector_list(request):
    sectors = CareerSector.objects.prefetch_related("career_paths").all()
    return render(request, "careers/sector_list.html", {"sectors": sectors})


@login_required
def sector_detail(request, pk):
    sector = get_object_or_404(CareerSector, pk=pk)
    paths = sector.career_paths.filter(is_active=True)
    return render(request, "careers/sector_detail.html", {"sector": sector, "paths": paths})


@login_required
def career_path_detail(request, pk):
    path = get_object_or_404(CareerPath, pk=pk, is_active=True)
    return render(request, "careers/career_path_detail.html", {"path": path})
