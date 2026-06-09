"""
careers/api_views.py
"""
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsAdmin
from apps.careers.models import CareerSector, CareerPath
from apps.careers.serializers import CareerSectorSerializer, CareerPathSerializer


class CareerSectorListView(ListCreateAPIView):
    queryset = CareerSector.objects.all()
    serializer_class = CareerSectorSerializer

    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "POST" else [IsAuthenticated()]


class CareerSectorDetailView(RetrieveUpdateDestroyAPIView):
    queryset = CareerSector.objects.all()
    serializer_class = CareerSectorSerializer

    def get_permissions(self):
        return [IsAdmin()] if self.request.method in ("PUT", "PATCH", "DELETE") else [IsAuthenticated()]


class CareerPathListView(ListCreateAPIView):
    serializer_class = CareerPathSerializer

    def get_queryset(self):
        qs = CareerPath.objects.select_related("sector").filter(is_active=True)
        sector = self.request.query_params.get("sector")
        if sector:
            qs = qs.filter(sector_id=sector)
        return qs

    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "POST" else [IsAuthenticated()]


class CareerPathDetailView(RetrieveUpdateDestroyAPIView):
    queryset = CareerPath.objects.select_related("sector").all()
    serializer_class = CareerPathSerializer

    def get_permissions(self):
        return [IsAdmin()] if self.request.method in ("PUT", "PATCH", "DELETE") else [IsAuthenticated()]
