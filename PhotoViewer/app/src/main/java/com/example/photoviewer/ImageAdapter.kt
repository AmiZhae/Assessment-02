package com.example.photoviewer

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.TextView
import android.widget.ToggleButton
import androidx.recyclerview.widget.RecyclerView
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors


data class PhotoPost(
    val id: Int,
    val title: String,
    val imageUrl: String,
    val description: String = ""
)

class ImageAdapter(
    private val onImageClick: (PhotoPost) -> Unit,
    private val onFavoriteClick: (PhotoPost) -> Unit
) : RecyclerView.Adapter<ImageAdapter.ImageViewHolder>() {

    private var posts: List<PhotoPost> = emptyList()
    private var favoriteKeys: Set<String> = emptySet()

    private val executor = Executors.newFixedThreadPool(3)
    private val imageCache = mutableMapOf<String, Bitmap>()

    class ImageViewHolder(view: View) :
        RecyclerView.ViewHolder(view) {

        val title: TextView =
            view.findViewById(R.id.txtTitle)

        val image: ImageView =
            view.findViewById(R.id.imgPost)

        val favorite: ToggleButton =
            view.findViewById(R.id.btnFavorite)
    }

    fun submitPosts(
        newPosts: List<PhotoPost>,
        favorites: Set<String>
    ) {
        posts = newPosts
        favoriteKeys = favorites
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(
        parent: ViewGroup,
        viewType: Int
    ): ImageViewHolder {

        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_image, parent, false)

        return ImageViewHolder(view)
    }

    override fun getItemCount(): Int = posts.size

    override fun onBindViewHolder(
        holder: ImageViewHolder,
        position: Int
    ) {
        val post = posts[position]

        holder.title.text = post.title

        holder.favorite.setOnCheckedChangeListener(null)

        val key = if (post.id > 0) {
            "id:${post.id}"
        } else {
            "url:${post.imageUrl}"
        }

        holder.favorite.isChecked = key in favoriteKeys

        holder.favorite.setOnCheckedChangeListener { _, _ ->
            onFavoriteClick(post)
        }

        holder.image.setOnClickListener {
            onImageClick(post)
        }

        holder.image.tag = post.imageUrl
        holder.image.setImageDrawable(null)

        if (post.imageUrl.isBlank()) return

        val cached = synchronized(imageCache) {
            imageCache[post.imageUrl]
        }

        if (cached != null) {
            holder.image.setImageBitmap(cached)
            return
        }

        executor.execute {
            var connection: HttpURLConnection? = null

            try {
                connection = URL(post.imageUrl)
                    .openConnection() as HttpURLConnection

                connection.connectTimeout = 5000
                connection.readTimeout = 10000

                val imageBytes = connection.inputStream.use {
                    it.readBytes()
                }

                val options = BitmapFactory.Options().apply {
                    inJustDecodeBounds = true
                }

                BitmapFactory.decodeByteArray(
                    imageBytes,
                    0,
                    imageBytes.size,
                    options
                )

                var sampleSize = 1

                while (
                    options.outWidth / sampleSize > 1024 ||
                    options.outHeight / sampleSize > 1024
                ) {
                    sampleSize *= 2
                }

                options.inJustDecodeBounds = false
                options.inSampleSize = sampleSize

                val bitmap = BitmapFactory.decodeByteArray(
                    imageBytes,
                    0,
                    imageBytes.size,
                    options
                )

                if (bitmap != null) {
                    synchronized(imageCache) {
                        imageCache[post.imageUrl] = bitmap
                    }

                    holder.image.post {
                        if (holder.image.tag == post.imageUrl) {
                            holder.image.setImageBitmap(bitmap)
                        }
                    }
                }

            } catch (e: Exception) {
                android.util.Log.e(
                    "ImageAdapter",
                    "Image download failed",
                    e
                )
            } finally {
                connection?.disconnect()
            }
        }
    }
}
