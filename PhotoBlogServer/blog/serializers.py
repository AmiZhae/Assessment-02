from rest_framework import serializers
from blog.models import Post


class PostSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(
        read_only=True
    )

    # The view handles duplicate detection.
    # Don't reject an existing event ID during
    # serializer validation.
    event_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        validators=[]
    )

    class Meta:
        model = Post

        fields = (
            'id',
            'author',
            'title',
            'text',
            'created_date',
            'published_date',
            'image',
            'event_id',
        )

        read_only_fields = (
            'id',
            'author',
            'created_date',
            'published_date',
        )
