from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path('', TemplateView.as_view(template_name='chat/index.html'), name='index'),
    path('chat/<slug:room_slug>/', TemplateView.as_view(template_name='chat/room.html'), name='chat-room'),
]
