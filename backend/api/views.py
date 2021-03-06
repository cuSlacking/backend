from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from django.views.generic import View
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

import qrcode
import qrcode.image.svg
import uuid
from io import BytesIO

from .serializers import UserSerializer, StoreSerializer, CodeSerializer
from .models import User, Store, Code

# pylint: disable=no-member
# Create your views here.
class UserViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    @action(methods=['GET'], detail=True)
    def get_favorites(self, request, pk=None):
        parsed = [StoreSerializer(i).data for i in request.user.favorites.all()]
        return JsonResponse({"list": parsed})

    @action(methods=['GET'], detail=True)
    def is_store_owner(self, request, pk=None):
        return JsonResponse({"result": request.user.is_store_owner})

    @action(methods=['GET'], detail=True)
    def is_vaccinated(self, request, pk=None):
        return JsonResponse({"result": request.user.vaccination_info})

class StoreViewSet(viewsets.ModelViewSet):
    queryset = Store.objects.all()
    serializer_class = StoreSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        if request.user.is_store_owner:
            Store.objects.create(
                name = request.POST.get("name"),
                phone = request.POST.get("phone"),
                safety_policy = request.POST.get("safety_policy"),
                location = request.POST.get("location"),
                store_hours = request.POST.get("store_hours"),
                owner = request.user,
            )
            
            return HttpResponse("Created :)", status=201)
        else:
            return HttpResponse("Unauthorized", status=401)


    @action(methods=['POST', 'GET'], detail=True)
    def retrieve_code(self, request, pk=None):
        codeUUID = uuid.uuid4()
        store = get_object_or_404(Store, pk=pk)

        Code.objects.create(uuid=codeUUID, store=store, user=request.user, in_store=False)

        return HttpResponse(str(codeUUID))

    @action(methods=['POST'], detail=True)
    def favorite(self, request, pk=None):
        store = get_object_or_404(Store, pk=pk)
        if store not in request.user.favorites.all():
            request.user.favorites.add(pk)
            return JsonResponse({
                "status": "success",
                "type": "add"
            })
        else: 
            request.user.favorites.remove(pk)
            return JsonResponse({
                "status": "success",
                "type": "remove"
            })

    @action(methods=['GET'], detail=True)
    def get_store_patreons(self, request, pk=None):
        store = get_object_or_404(Store, pk=pk)
        codes = Code.objects.filter(
            Q(store=store) & Q(in_store=True)
        ).all()
        return JsonResponse({
            "num": str(len(codes))
        })

class CodeViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    queryset = Code.objects.all()
    serializer_class = CodeSerializer
    permission_classes = [IsAuthenticated]

    @action(methods=['POST'], detail=True)
    def enter(self, request, pk=None):
        code = get_object_or_404(Code, uuid=pk)

        if not code.in_store:
            code.in_store = True
            code.save()
            return JsonResponse({
                "success": "true",
                "status": "enter"
            })
        else:
            code.delete()
            return JsonResponse({
                "success": "true",
                "status": "exit"
            })

    @action(methods=['GET'], detail=True, url_path="qr.png")
    def _generate(self, request, pk=None):
        byte_io = BytesIO()
        qrImg = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qrImg.add_data(pk)
        qrImg.make(fit=True)

        img = qrImg.make_image(fill_color="black", back_color="white")
        img.save(byte_io, 'PNG')
        return HttpResponse(byte_io.getvalue(), content_type="image/jpeg")

