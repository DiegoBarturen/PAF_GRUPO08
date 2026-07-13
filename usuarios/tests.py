from django.test import TestCase
from django.contrib.auth import authenticate
from django.contrib.messages import get_messages
from django.urls import reverse
from usuarios.models import Usuario

class CaseInsensitiveAuthTest(TestCase):
    def setUp(self):
        # Create a user with mixed casing
        self.user = Usuario.objects.create_user(
            username="TestUser",
            email="test@example.com",
            password="Password123!",
            rol="cliente"
        )

    def test_case_insensitive_authentication(self):
        # Test authenticating with exact casing
        user = authenticate(username="TestUser", password="Password123!")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "TestUser")

        # Test authenticating with lowercase
        user_lower = authenticate(username="testuser", password="Password123!")
        self.assertIsNotNone(user_lower)
        self.assertEqual(user_lower.username, "TestUser")

        # Test authenticating with uppercase
        user_upper = authenticate(username="TESTUSER", password="Password123!")
        self.assertIsNotNone(user_upper)
        self.assertEqual(user_upper.username, "TestUser")

    def test_case_sensitive_password(self):
        # Password with incorrect casing should fail authentication
        user = authenticate(username="TestUser", password="password123!")
        self.assertIsNone(user)

    def test_case_insensitive_registration_conflict(self):
        # Try to register a user with the same name but in lowercase
        response = self.client.post(reverse("registro"), {
            "username": "testuser",
            "email": "another@example.com",
            "password": "Password123!",
            "rol": "cliente"
        })
        # It should redirect back to registry and set an error message
        self.assertEqual(response.status_code, 302)
        
        # Verify the user was NOT created
        self.assertFalse(Usuario.objects.filter(email="another@example.com").exists())

class NegocioProfileRequiredTest(TestCase):
    def setUp(self):
        # Create a business user
        self.negocio_user = Usuario.objects.create_user(
            username="business_user",
            email="business@example.com",
            password="Password123!",
            rol="negocio"
        )

    def test_redirection_without_profile(self):
        # Log in the business user
        login_success = self.client.login(username="business_user", password="Password123!")
        self.assertTrue(login_success)

        # Check redirection after login (should redirect to registrar_negocio)
        response = self.client.post(reverse("login"), {
            "username": "business_user",
            "password": "Password123!"
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("registrar_negocio"), response.url)

        # Attempting to access orders panel should redirect to registrar_negocio
        response = self.client.get(reverse("pedidos:panel_negocio"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("registrar_negocio"), response.url)

        # Attempting to access product admin should redirect to registrar_negocio
        response = self.client.get(reverse("administrar_productos"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("registrar_negocio"), response.url)

    def test_access_with_profile(self):
        # Create a business profile for this user
        from catalogo.models import Negocio
        Negocio.objects.create(
            propietario=self.negocio_user,
            nombre_comercial="Test Restaurant",
            descripcion="A test restaurant",
            direccion="123 Test St",
            telefono="123456789",
            rubro="restaurante"
        )

        # Log in the business user
        login_success = self.client.login(username="business_user", password="Password123!")
        self.assertTrue(login_success)

        # Login post request should redirect to panel_negocio
        response = self.client.post(reverse("login"), {
            "username": "business_user",
            "password": "Password123!"
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("pedidos:panel_negocio"), response.url)

        # Accessing orders panel should succeed (return 200)
        response = self.client.get(reverse("pedidos:panel_negocio"))
        self.assertEqual(response.status_code, 200)

        # Accessing product admin should succeed (return 200)
        response = self.client.get(reverse("administrar_productos"))
        self.assertEqual(response.status_code, 200)

