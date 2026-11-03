
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Post


class PostModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="testpassword123"
        )

    def test_create_post(self):
        post = Post.objects.create(
            author=self.user,
            title="Test Post",
            text="Testing Django Post model"
        )

        self.assertEqual(post.title, "Test Post")
        self.assertEqual(str(post), "Test Post")

    def test_publish_post(self):
        post = Post.objects.create(
            author=self.user,
            title="Publish Test",
            text="Testing publish method"
        )

        post.publish()

        self.assertIsNotNone(post.published_date)


class PostAPITests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username="apiuser",
            password="testpassword123"
        )

        self.post = Post.objects.create(
            author=self.user,
            title="API Test Post",
            text="Testing GET API",
            published_date=timezone.now()
        )

        self.url = "/api_root/Post/"

    def test_get_posts(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_get_post_detail(self):
        response = self.client.get(
            f"{self.url}{self.post.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["title"],
            "API Test Post"
        )

    def test_post_fields(self):
        response = self.client.get(self.url)
        post_data = response.data[0]

        self.assertIn("author", post_data)
        self.assertIn("title", post_data)
        self.assertIn("text", post_data)
        self.assertIn("image", post_data)

    def test_create_post_api(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {
                "author": self.user.pk,
                "title": "New API Post",
                "text": "Created by automated test",
                "published_date": timezone.now().isoformat()
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, 201)

        self.assertTrue(
            Post.objects.filter(
                title="New API Post"
            ).exists()
        )

    def test_invalid_post(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            {
                "author": self.user.pk,
                "title": "",
                "text": "Invalid post"
            },
            format="multipart"
        )

        self.assertEqual(response.status_code, 400)


class BlogViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="viewtestuser",
            password="testpassword123"
        )

        self.post = Post.objects.create(
            author=self.user,
            title="Original Blog Post",
            text="This is a test blog post.",
            published_date=timezone.now()
        )

        self.client.force_login(self.user)

    def test_post_list(self):
        response = self.client.get(
            reverse("post_list")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Original Blog Post"
        )

    def test_post_detail(self):
        response = self.client.get(
            reverse(
                "post_detail",
                kwargs={"pk": self.post.pk}
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Original Blog Post"
        )

    def test_post_detail_not_found(self):
        response = self.client.get(
            reverse(
                "post_detail",
                kwargs={"pk": 99999}
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_post_new_get(self):
        response = self.client.get(
            reverse("post_new")
        )

        self.assertEqual(response.status_code, 200)

    def test_post_new_post(self):
        response = self.client.post(
            reverse("post_new"),
            {
                "title": "New Blog Post",
                "text": "Created using automated test."
            }
        )

        self.assertEqual(response.status_code, 302)

        self.assertTrue(
            Post.objects.filter(
                title="New Blog Post"
            ).exists()
        )

    def test_post_edit_get(self):
        response = self.client.get(
            reverse(
                "post_edit",
                kwargs={"pk": self.post.pk}
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_post_edit_post(self):
        response = self.client.post(
            reverse(
                "post_edit",
                kwargs={"pk": self.post.pk}
            ),
            {
                "title": "Updated Blog Post",
                "text": "This post has been updated."
            }
        )

        self.assertEqual(response.status_code, 302)

        self.post.refresh_from_db()

        self.assertEqual(
            self.post.title,
            "Updated Blog Post"
        )

    def test_post_edit_not_found(self):
        response = self.client.get(
            reverse(
                "post_edit",
                kwargs={"pk": 99999}
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_js_test(self):
        response = self.client.get(
            reverse("js_test")
        )

        self.assertEqual(response.status_code, 200)

    def test_post_list_excludes_unpublished(self):
        Post.objects.create(
            author=self.user,
            title="Unpublished Blog Post",
            text="This should not appear.",
            published_date=None
        )

        response = self.client.get(
            reverse("post_list")
        )

        self.assertEqual(response.status_code, 200)

        self.assertNotContains(
            response,
            "Unpublished Blog Post"
        )

    def test_post_new_invalid(self):
        response = self.client.post(
            reverse("post_new"),
            {
                "title": "",
                "text": "Invalid post"
            }
        )

        self.assertEqual(response.status_code, 200)

    def test_post_edit_invalid(self):
        response = self.client.post(
            reverse(
                "post_edit",
                kwargs={"pk": self.post.pk}
            ),
            {
                "title": "",
                "text": "Invalid update"
            }
        )

        self.assertEqual(response.status_code, 200)
