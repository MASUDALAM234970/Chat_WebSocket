"""
Authentication and user management API views.
"""

from django.contrib.auth import get_user_model
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiExample

from .serializers import (
    UserRegistrationSerializer,
    UserProfileSerializer,
    UserPublicSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
)

User = get_user_model()


@extend_schema(tags=['Auth'])
class RegisterView(generics.CreateAPIView):
    """
    Register a new user account.
    Returns the created user object (no token — login separately).
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            'message': 'User registered successfully.',
            'user': UserProfileSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Auth'])
class LoginView(TokenObtainPairView):
    """
    Authenticate with email & password.
    Returns access + refresh JWT tokens along with user data.
    """
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]


@extend_schema(tags=['Auth'])
class LogoutView(APIView):
    """Blacklist the refresh token (logout)."""

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if not refresh_token:
                return Response(
                    {'error': 'refresh_token is required.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=['Users'])
class UserProfileView(generics.RetrieveUpdateAPIView):
    """Get or update the authenticated user's own profile."""

    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user


@extend_schema(tags=['Users'])
class UserListView(generics.ListAPIView):
    """List all registered users (for starting new chats)."""

    serializer_class = UserPublicSerializer

    def get_queryset(self):
        return User.objects.exclude(id=self.request.user.id).order_by('-is_online', 'username')


@extend_schema(tags=['Users'])
class UserDetailView(generics.RetrieveAPIView):
    """Get public profile of a specific user by ID."""

    serializer_class = UserPublicSerializer
    queryset = User.objects.all()


@extend_schema(tags=['Auth'])
class ChangePasswordView(APIView):
    """Change the authenticated user's password."""

    def put(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'error': 'Old password is incorrect.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'message': 'Password changed successfully.'})
