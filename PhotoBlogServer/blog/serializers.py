
from rest_framework import serializers
from blog.models import Post


class PostSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField(read_only=True)

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
        )
        read_only_fields = (
            'id',
            'author',
            'created_date',
            'published_date',
        )
