from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def home(request):
    # Minimal context so template can render; real KPIs are computed elsewhere
    context = {
        'total_cases': 0,
        'total_students': 0,
        'cases_by_status': {},
        'cases_by_risk': {},
        'active_alerts': [],
    }
    return render(request, 'dashboard/home.html', context)
