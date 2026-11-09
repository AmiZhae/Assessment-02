from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db import IntegrityError, transaction

from rest_framework import viewsets, status
from rest_framework.authentication import (
    TokenAuthentication,
    SessionAuthentication,
)
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.parsers import (
    MultiPartParser,
    FormParser,
    JSONParser,
)
from rest_framework.response import Response

from .models import Post
from .forms import PostForm
from .serializers import PostSerializer


def post_list(request):
    posts = Post.objects.filter(
        published_date__lte=timezone.now()
    ).order_by('-published_date')

    return render(
        request,
        'blog/post_list.html',
        {'posts': posts}
    )


def post_detail(request, pk):
    post = get_object_or_404(Post, pk=pk)

    return render(
        request,
        'blog/post_detail.html',
        {'post': post}
    )


def post_new(request):
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)

        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.published_date = timezone.now()
            post.save()

            return redirect('post_detail', pk=post.pk)
    else:
        form = PostForm()

    return render(
        request,
        'blog/post_edit.html',
        {'form': form}
    )


def post_edit(request, pk):
    post = get_object_or_404(Post, pk=pk)

    if request.method == "POST":
        form = PostForm(
            request.POST,
            request.FILES,
            instance=post
        )

        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.published_date = timezone.now()
            post.save()

            return redirect('post_detail', pk=post.pk)
    else:
        form = PostForm(instance=post)

    return render(
        request,
        'blog/post_edit.html',
        {'form': form}
    )


def js_test(request):
    return render(request, 'blog/js_test.html', {})


class IntruderImages(viewsets.ModelViewSet):
    name = "Intruder Image List"

    queryset = Post.objects.all().order_by('-created_date')
    serializer_class = PostSerializer

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
    ]

    permission_classes = [
        IsAuthenticatedOrReadOnly,
    ]

    parser_classes = [
        MultiPartParser,
        FormParser,
        JSONParser,
    ]

    def perform_create(self, serializer):
        serializer.save(
            author=self.request.user,
            published_date=timezone.now()
        )

    def create(self, request, *args, **kwargs):
        event_id = request.data.get('event_id')

        # If an event ID was supplied, validate it
        # before checking for duplicates.
        if event_id:
            from uuid import UUID

            try:
                event_id = UUID(str(event_id))
            except (ValueError, AttributeError, TypeError):
                return Response(
                    {'event_id': ['Invalid UUID.']},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Only treat records belonging to the
            # authenticated uploader as duplicates.
            existing = Post.objects.filter(
                event_id=event_id,
                author=request.user
            ).first()

            if existing:
                serializer = self.get_serializer(existing)
                return Response(
                    serializer.data,
                    status=status.HTTP_200_OK
                )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                self.perform_create(serializer)
        except IntegrityError:
            # Handles concurrent retries of the
            # same event ID.
            existing = Post.objects.filter(
                event_id=event_id,
                author=request.user
            ).first() if event_id else None

            if existing:
                return Response(
                    self.get_serializer(existing).data,
                    status=status.HTTP_200_OK
                )

            raise

        headers = self.get_success_headers(serializer.data)

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )
