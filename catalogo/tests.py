from django.test import TestCase
from decimal import Decimal
from django.urls import reverse
from usuarios.models import Usuario
from catalogo.models import Categoria, Negocio
from catalogo.forms import ProductoForm

class ProductFormCategoryFilterTest(TestCase):
    def setUp(self):
        # Create categories for different rubros
        self.cat_food = Categoria.objects.create(nombre="Main Dishes", rubro="restaurante", activa=True)
        self.cat_pet = Categoria.objects.create(nombre="Dog Food", rubro="mascotas", activa=True)
        
        # Create a business user for a restaurant
        self.restaurant_user = Usuario.objects.create_user(
            username="restaurant_owner",
            email="rest@example.com",
            password="password",
            rol="negocio"
        )
        self.restaurant_negocio = Negocio.objects.create(
            propietario=self.restaurant_user,
            nombre_comercial="My Restaurant",
            descripcion="Tasty food",
            direccion="Street 123",
            telefono="123456",
            rubro="restaurante"
        )

    def test_form_filters_categories_by_user_rubro(self):
        # Initialize the form with a business user
        form = ProductoForm(user=self.restaurant_user)
        
        # Get the categories from the form queryset
        form_categories = list(form.fields["categoria"].queryset)
        
        # Verify only the restaurant category is shown, pet category is hidden
        self.assertIn(self.cat_food, form_categories)
        self.assertNotIn(self.cat_pet, form_categories)

class HomepageFilteringTest(TestCase):
    def setUp(self):
        from catalogo.models import Producto

        # Create two business owners
        self.owner1 = Usuario.objects.create_user(username="owner1", email="owner1@ex.com", password="pwd", rol="negocio")
        self.owner2 = Usuario.objects.create_user(username="owner2", email="owner2@ex.com", password="pwd", rol="negocio")

        # Create a restaurant business
        self.restaurant = Negocio.objects.create(
            propietario=self.owner1,
            nombre_comercial="Restaurant Negocio",
            descripcion="Food business",
            direccion="Addr 1",
            telefono="111",
            rubro="restaurante"
        )
        # Create a pet shop business
        self.petshop = Negocio.objects.create(
            propietario=self.owner2,
            nombre_comercial="PetShop Negocio",
            descripcion="Pet business",
            direccion="Addr 2",
            telefono="222",
            rubro="mascotas"
        )

        from catalogo.models import Valoracion
        # Create a customer user to make the ratings
        self.customer = Usuario.objects.create_user(username="customer", email="cust@ex.com", password="pwd", rol="cliente")
        
        # Create a rating for the restaurant
        Valoracion.objects.create(
            negocio=self.restaurant,
            cliente=self.customer,
            puntuacion=5,
            comentario="Great!"
        )
        
        # Create a rating for the pet shop
        Valoracion.objects.create(
            negocio=self.petshop,
            cliente=self.customer,
            puntuacion=4,
            comentario="Nice!"
        )

        # Create product in offer for restaurant
        self.prod_offer_rest = Producto.objects.create(
            negocio=self.restaurant,
            nombre="Burger",
            descripcion="Cheesy burger",
            precio=Decimal("20.00"),
            descuento_porcentaje=20,
            disponible=True,
            stock=10
        )
        # Create product in offer for pet shop
        self.prod_offer_pet = Producto.objects.create(
            negocio=self.petshop,
            nombre="Dog Toy",
            descripcion="Bouncy toy",
            precio=Decimal("15.00"),
            descuento_porcentaje=10,
            disponible=True,
            stock=5
        )

    def test_homepage_all_rubros(self):
        # Fetch the homepage without any rubro filter
        response = self.client.get(reverse("home_negocios"))
        self.assertEqual(response.status_code, 200)

        # Both offers should be visible
        offers = list(response.context["productos_oferta"])
        self.assertIn(self.prod_offer_rest, offers)
        self.assertIn(self.prod_offer_pet, offers)

        # Both businesses should be visible in community favorites
        favorites = list(response.context["negocios_mejor_valorados"])
        self.assertIn(self.restaurant, favorites)
        self.assertIn(self.petshop, favorites)

    def test_homepage_filtered_by_restaurante(self):
        # Fetch homepage filtered by restaurante
        response = self.client.get(reverse("home_negocios"), {"rubro": "restaurante"})
        self.assertEqual(response.status_code, 200)

        # Only restaurant offer should be visible
        offers = list(response.context["productos_oferta"])
        self.assertIn(self.prod_offer_rest, offers)
        self.assertNotIn(self.prod_offer_pet, offers)

        # Only restaurant business should be in community favorites
        favorites = list(response.context["negocios_mejor_valorados"])
        self.assertIn(self.restaurant, favorites)
        self.assertNotIn(self.petshop, favorites)

    def test_homepage_filtered_by_mascotas(self):
        # Fetch homepage filtered by mascotas
        response = self.client.get(reverse("home_negocios"), {"rubro": "mascotas"})
        self.assertEqual(response.status_code, 200)

        # Only pet offer should be visible
        offers = list(response.context["productos_oferta"])
        self.assertNotIn(self.prod_offer_rest, offers)
        self.assertIn(self.prod_offer_pet, offers)

        # Only pet business should be in community favorites
        favorites = list(response.context["negocios_mejor_valorados"])
        self.assertNotIn(self.restaurant, favorites)
        self.assertIn(self.petshop, favorites)

