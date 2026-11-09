package com.example.photoviewer

import android.animation.ValueAnimator
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import com.google.android.material.floatingactionbutton.FloatingActionButton
import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONTokener
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

class MainActivity : AppCompatActivity() {

    private val serverUrl =  "https://amirulzharif.pythonanywhere.com/api_root/Post/"

    private lateinit var txtStatus: TextView
    private lateinit var txtCount: TextView
    private lateinit var recyclerView: RecyclerView
    private lateinit var imageAdapter: ImageAdapter
    private lateinit var swipeRefresh: SwipeRefreshLayout
    private lateinit var editSearch: EditText
    private lateinit var btnSort: TextView
    private lateinit var fabFavorites: FloatingActionButton
    private lateinit var collapsibleHeader: View

    private var allPosts: List<PhotoPost> = emptyList()
    private var newestFirst = true
    private var favoritesOnly = false

    private val favoriteKeys = mutableSetOf<String>()

    private val preferences by lazy {
        getSharedPreferences("photo_favorites", MODE_PRIVATE)
    }

    private var headerExpandedHeight = 0
    private var headerHidden = false
    private var headerAnimator: ValueAnimator? = null
    private var scrollDistance = 0

    private var selectedImageUri: Uri? = null
    private var uploadPreview: ImageView? = null
    private var selectedImageLabel: TextView? = null

    private val imagePicker = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri ->

        selectedImageUri = uri

        if (uri != null) {
            uploadPreview?.setImageURI(uri)
            selectedImageLabel?.text = "Image selected"
        } else {
            selectedImageLabel?.text = "No image selected"
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        txtStatus = findViewById(R.id.txtStatus)
        txtCount = findViewById(R.id.txtCount)
        recyclerView = findViewById(R.id.recyclerView)
        swipeRefresh = findViewById(R.id.swipeRefresh)
        editSearch = findViewById(R.id.editSearch)
        btnSort = findViewById(R.id.btnSort)
        fabFavorites = findViewById(R.id.fabFavorites)
        collapsibleHeader = findViewById(R.id.collapsibleHeader)

        favoriteKeys.addAll(
            preferences.getStringSet(
                "favorites",
                emptySet()
            ) ?: emptySet()
        )

        recyclerView.layoutManager =
            LinearLayoutManager(this)

        imageAdapter = ImageAdapter(
            onImageClick = { post ->
                showFullScreenImage(post)
            },
            onFavoriteClick = { post ->
                toggleFavorite(post)
            }
        )

        recyclerView.adapter = imageAdapter

        collapsibleHeader.post {
            headerExpandedHeight = collapsibleHeader.height
        }

        findViewById<Button>(R.id.btnSync).setOnClickListener {
            syncPhotos()
        }

        findViewById<Button>(R.id.btnUpload).setOnClickListener {
            showUploadDialog()
        }

        swipeRefresh.setOnRefreshListener {
            syncPhotos()
        }

        editSearch.addTextChangedListener(
            object : TextWatcher {

                override fun beforeTextChanged(
                    s: CharSequence?,
                    start: Int,
                    count: Int,
                    after: Int
                ) {}

                override fun onTextChanged(
                    s: CharSequence?,
                    start: Int,
                    before: Int,
                    count: Int
                ) {
                    updateVisiblePosts()
                }

                override fun afterTextChanged(
                    s: Editable?
                ) {}
            }
        )

        btnSort.setOnClickListener {
            val options = arrayOf(
                "Newest first",
                "Oldest first"
            )

            AlertDialog.Builder(this)
                .setTitle("Sort Photos")
                .setSingleChoiceItems(
                    options,
                    if (newestFirst) 0 else 1
                ) { dialog, which ->

                    newestFirst = which == 0
                    updateVisiblePosts()
                    dialog.dismiss()
                }
                .setNegativeButton("Cancel", null)
                .show()
        }

        fabFavorites.setOnClickListener {
            favoritesOnly = !favoritesOnly
            updateVisiblePosts()
        }

        recyclerView.addOnScrollListener(
            object : RecyclerView.OnScrollListener() {

                override fun onScrolled(
                    recyclerView: RecyclerView,
                    dx: Int,
                    dy: Int
                ) {
                    super.onScrolled(recyclerView, dx, dy)

                    if (dy == 0) return

                    scrollDistance += dy

                    if (scrollDistance > 18) {
                        setHeaderHidden(true)
                        scrollDistance = 0
                    } else if (scrollDistance < -18) {
                        setHeaderHidden(false)
                        scrollDistance = 0
                    }
                }
            }
        )

        updateVisiblePosts()
    }

    private fun setHeaderHidden(hidden: Boolean) {
        if (headerHidden == hidden) return

        if (!hidden && headerExpandedHeight == 0) {
            collapsibleHeader.measure(
                View.MeasureSpec.makeMeasureSpec(
                    (collapsibleHeader.parent as View).width,
                    View.MeasureSpec.EXACTLY
                ),
                View.MeasureSpec.makeMeasureSpec(
                    0,
                    View.MeasureSpec.UNSPECIFIED
                )
            )

            headerExpandedHeight =
                collapsibleHeader.measuredHeight
        }

        if (headerExpandedHeight == 0) return

        headerHidden = hidden
        headerAnimator?.cancel()

        val startHeight = collapsibleHeader.height

        val endHeight = if (hidden) {
            0
        } else {
            headerExpandedHeight
        }

        headerAnimator = ValueAnimator.ofInt(
            startHeight,
            endHeight
        ).apply {

            duration = 220

            addUpdateListener { animation ->
                val height = animation.animatedValue as Int

                val params = collapsibleHeader.layoutParams
                params.height = height
                collapsibleHeader.layoutParams = params

                collapsibleHeader.alpha =
                    if (headerExpandedHeight > 0) {
                        height.toFloat() / headerExpandedHeight
                    } else {
                        1f
                    }
            }

            start()
        }
    }

    private fun favoriteKey(post: PhotoPost): String {
        return if (post.id > 0) {
            "id:${post.id}"
        } else {
            "url:${post.imageUrl}"
        }
    }

    private fun toggleFavorite(post: PhotoPost) {
        val key = favoriteKey(post)

        if (!favoriteKeys.add(key)) {
            favoriteKeys.remove(key)
        }

        preferences.edit()
            .putStringSet(
                "favorites",
                favoriteKeys.toSet()
            )
            .apply()

        updateVisiblePosts()
    }

    private fun updateVisiblePosts() {
        val query = editSearch.text.toString().trim()

        val filtered = allPosts
            .asSequence()
            .filter {
                it.title.contains(
                    query,
                    ignoreCase = true
                )
            }
            .filter {
                !favoritesOnly ||
                        favoriteKey(it) in favoriteKeys
            }
            .sortedWith(
                if (newestFirst) {
                    compareByDescending<PhotoPost> {
                        it.id
                    }
                } else {
                    compareBy<PhotoPost> {
                        it.id
                    }
                }
            )
            .toList()

        imageAdapter.submitPosts(
            filtered,
            favoriteKeys.toSet()
        )

        btnSort.text = if (newestFirst) {
            "↕ Newest first"
        } else {
            "↕ Oldest first"
        }

        txtCount.text =
            "Showing ${filtered.size} of ${allPosts.size} posts"

        fabFavorites.contentDescription =
            if (favoritesOnly) {
                "Show all photos"
            } else {
                "Show favorite photos"
            }

        fabFavorites.alpha =
            if (favoritesOnly) 1f else 0.8f
    }

    private fun showFullScreenImage(post: PhotoPost) {

        val density = resources.displayMetrics.density

        fun dp(value: Int): Int {
            return (value * density).toInt()
        }

        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(
                dp(16),
                dp(8),
                dp(16),
                dp(12)
            )
        }

        val imageView = ImageView(this).apply {
            adjustViewBounds = true
            scaleType = ImageView.ScaleType.FIT_CENTER
            contentDescription = post.title

            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                dp(320)
            )
        }

        val titleView = TextView(this).apply {
            text = post.title
            textSize = 20f

            setTypeface(
                null,
                android.graphics.Typeface.BOLD
            )

            setPadding(
                0,
                dp(16),
                0,
                dp(8)
            )
        }

        val descriptionView = TextView(this).apply {
            text = post.description.ifBlank {
                "No description available."
            }

            textSize = 15f

            setLineSpacing(
                dp(3).toFloat(),
                1f
            )

            setPadding(
                0,
                0,
                0,
                dp(12)
            )
        }

        container.addView(imageView)
        container.addView(titleView)
        container.addView(descriptionView)

        val scrollView = ScrollView(this).apply {
            isFillViewport = false
            addView(container)
        }

        val dialog = AlertDialog.Builder(this)
            .setView(scrollView)
            .setPositiveButton("Close", null)
            .create()

        dialog.show()

        val maxHeight = (
                resources.displayMetrics.heightPixels * 0.85f
                ).toInt()

        dialog.window?.setLayout(
            (
                    resources.displayMetrics.widthPixels * 0.95f
                    ).toInt(),
            maxHeight
        )

        if (post.imageUrl.isBlank()) {
            return
        }

        Thread {
            var connection: HttpURLConnection? = null

            try {
                connection = URL(post.imageUrl)
                    .openConnection() as HttpURLConnection

                connection.connectTimeout = 7000
                connection.readTimeout = 15000

                val bytes = connection.inputStream.use {
                    it.readBytes()
                }

                val bounds = BitmapFactory.Options().apply {
                    inJustDecodeBounds = true
                }

                BitmapFactory.decodeByteArray(
                    bytes,
                    0,
                    bytes.size,
                    bounds
                )

                var sample = 1

                while (
                    bounds.outWidth / sample > 2048 ||
                    bounds.outHeight / sample > 2048
                ) {
                    sample *= 2
                }

                val options = BitmapFactory.Options().apply {
                    inSampleSize = sample
                }

                val bitmap = BitmapFactory.decodeByteArray(
                    bytes,
                    0,
                    bytes.size,
                    options
                )

                runOnUiThread {
                    if (
                        dialog.isShowing &&
                        bitmap != null
                    ) {
                        imageView.setImageBitmap(bitmap)
                    }
                }

            } catch (e: Exception) {
                Log.e(
                    "PhotoViewer",
                    "Full-screen image failed",
                    e
                )

                runOnUiThread {
                    if (dialog.isShowing) {
                        txtStatus.text =
                            "Image could not be opened"
                    }
                }

            } finally {
                connection?.disconnect()
            }
        }.start()
    }

    private fun syncPhotos() {
        txtStatus.text = "Synchronizing photos..."
        swipeRefresh.isRefreshing = true

        Thread {
            var connection: HttpURLConnection? = null

            try {
                val conn = URL(serverUrl)
                    .openConnection() as HttpURLConnection

                connection = conn
                conn.requestMethod = "GET"
                conn.connectTimeout = 5000
                conn.readTimeout = 10000

                conn.setRequestProperty(
                    "Accept",
                    "application/json"
                )

                val responseCode = conn.responseCode

                if (responseCode !in 200..299) {
                    throw Exception(
                        "HTTP $responseCode"
                    )
                }

                val response = conn.inputStream
                    .bufferedReader()
                    .use {
                        it.readText()
                    }

                val json = JSONTokener(response).nextValue()

                val postsArray: JSONArray = when (json) {

                    is JSONArray -> json

                    is JSONObject ->
                        json.optJSONArray("results")
                            ?: throw Exception(
                                "No results found"
                            )

                    else -> throw Exception(
                        "Invalid JSON response"
                    )
                }

                val posts = mutableListOf<PhotoPost>()

                for (i in 0 until postsArray.length()) {

                    val post = postsArray.getJSONObject(i)

                    val title = post.optString(
                        "title",
                        "Untitled"
                    )

                    val description = post.optString(
                        "text",
                        ""
                    )

                    val rawImageUrl = post.optString(
                        "image",
                        ""
                    )

                    val imageUrl = when {
                        rawImageUrl.isBlank() ||
                                rawImageUrl == "null" -> ""

                        rawImageUrl.startsWith("http://") ||
                                rawImageUrl.startsWith("https://") ->
                            rawImageUrl

                        else -> URL(
                            URL(serverUrl),
                            rawImageUrl
                        ).toString()
                    }

                    posts.add(
                        PhotoPost(
                            id = post.optInt(
                                "id",
                                i + 1
                            ),
                            title = title,
                            imageUrl = imageUrl,
                            description = description
                        )
                    )
                }

                runOnUiThread {
                    allPosts = posts
                    updateVisiblePosts()

                    txtStatus.text =
                        "Sync complete: ${posts.size} posts"
                }

            } catch (e: Exception) {
                Log.e(
                    "PhotoViewer",
                    "Sync failed",
                    e
                )

                runOnUiThread {
                    txtStatus.text =
                        "Sync failed: ${e.message}"
                }

            } finally {
                connection?.disconnect()

                runOnUiThread {
                    swipeRefresh.isRefreshing = false
                }
            }
        }.start()
    }

    private fun showUploadDialog() {
        selectedImageUri = null

        val view = layoutInflater.inflate(
            R.layout.dialog_upload,
            null
        )

        val editTitle = view.findViewById<EditText>(
            R.id.editTitle
        )

        val editDescription = view.findViewById<EditText>(
            R.id.editDescription
        )

        uploadPreview = view.findViewById(
            R.id.imgPreview
        )

        selectedImageLabel = view.findViewById(
            R.id.txtSelectedImage
        )

        view.findViewById<Button>(
            R.id.btnSelectImage
        ).setOnClickListener {
            imagePicker.launch("image/*")
        }

        val dialog = AlertDialog.Builder(this)
            .setTitle("Upload New Photo")
            .setView(view)
            .setNegativeButton("Cancel", null)
            .setPositiveButton("Submit Post", null)
            .create()

        dialog.setOnShowListener {

            dialog.getButton(
                AlertDialog.BUTTON_POSITIVE
            ).setOnClickListener {

                val title = editTitle.text
                    .toString()
                    .trim()

                val description = editDescription.text
                    .toString()
                    .trim()

                val imageUri = selectedImageUri

                when {

                    title.isEmpty() -> {
                        editTitle.error =
                            "Title is required"
                    }

                    description.isEmpty() -> {
                        editDescription.error =
                            "Description is required"
                    }

                    imageUri == null -> {
                        selectedImageLabel?.text =
                            "Please select an image"
                    }

                    else -> {
                        uploadPost(
                            title,
                            description,
                            imageUri
                        )

                        dialog.dismiss()
                    }
                }
            }
        }

        dialog.setOnDismissListener {
            uploadPreview = null
            selectedImageLabel = null
        }

        dialog.show()
    }

    private fun uploadPost(
        title: String,
        description: String,
        imageUri: Uri
    ) {
        txtStatus.text = "Uploading photo..."

        Thread {
            var connection: HttpURLConnection? = null

            try {
                val boundary =
                    "PhotoViewer-${UUID.randomUUID()}"

                val conn = URL(serverUrl)
                    .openConnection() as HttpURLConnection

                connection = conn
                conn.requestMethod = "POST"
                conn.doOutput = true
                conn.connectTimeout = 10000
                conn.readTimeout = 30000

                conn.setRequestProperty(
                    "Content-Type",
                    "multipart/form-data; boundary=$boundary"
                )

                conn.setRequestProperty(
                    "Accept",
                    "application/json"
                )

                val mimeType =
                    contentResolver.getType(imageUri)
                        ?: "image/jpeg"

                val extension = when (mimeType) {
                    "image/png" -> "png"
                    "image/webp" -> "webp"
                    "image/gif" -> "gif"
                    else -> "jpg"
                }

                val filename =
                    "android_photo_${System.currentTimeMillis()}.$extension"

                conn.outputStream.use { output ->

                    fun write(value: String) {
                        output.write(
                            value.toByteArray(
                                Charsets.UTF_8
                            )
                        )
                    }

                    fun writeField(
                        name: String,
                        value: String
                    ) {
                        write("--$boundary\r\n")

                        write(
                            "Content-Disposition: form-data; " +
                                    "name=\"$name\"\r\n\r\n"
                        )

                        write("$value\r\n")
                    }

                    writeField("author", "1")
                    writeField("title", title)
                    writeField("text", description)

                    write("--$boundary\r\n")

                    write(
                        "Content-Disposition: form-data; " +
                                "name=\"image\"; " +
                                "filename=\"$filename\"\r\n"
                    )

                    write(
                        "Content-Type: $mimeType\r\n\r\n"
                    )

                    val input = contentResolver
                        .openInputStream(imageUri)
                        ?: throw Exception(
                            "Cannot read selected image"
                        )

                    input.use {
                        it.copyTo(output)
                    }

                    write("\r\n")
                    write("--$boundary--\r\n")
                }

                val responseCode = conn.responseCode

                val responseBody = (
                        if (responseCode in 200..299) {
                            conn.inputStream
                        } else {
                            conn.errorStream
                        }
                        )?.bufferedReader()?.use {
                        it.readText()
                    }.orEmpty()

                Log.d(
                    "PhotoUpload",
                    "HTTP $responseCode: $responseBody"
                )

                if (responseCode in 200..299) {
                    runOnUiThread {
                        txtStatus.text =
                            "Upload successful!"
                        syncPhotos()
                    }
                } else {
                    runOnUiThread {
                        txtStatus.text =
                            "Upload failed: HTTP $responseCode"
                    }
                }

            } catch (e: Exception) {
                Log.e(
                    "PhotoUpload",
                    "Upload failed",
                    e
                )

                runOnUiThread {
                    txtStatus.text =
                        "Upload failed: ${e.message}"
                }

            } finally {
                connection?.disconnect()
            }
        }.start()
    }
}
