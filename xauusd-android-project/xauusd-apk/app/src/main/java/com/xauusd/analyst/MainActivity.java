package com.xauusd.analyst;

import android.annotation.SuppressLint;
import android.app.AlertDialog;
import android.content.Context;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.os.Build;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private SwipeRefreshLayout swipeRefresh;

    // Default server — bisa diubah di app via dialog
    private static final String PREF_KEY_URL = "server_url";
    private static final String DEFAULT_URL  = "http://192.168.1.5:8000";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView      = findViewById(R.id.webview);
        swipeRefresh = findViewById(R.id.swipe_refresh);

        setupWebView();
        setupSwipeRefresh();

        String url = getSavedUrl();
        loadUrl(url);
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void setupWebView() {
        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setSupportZoom(false);

        // User agent — supaya server tahu ini WebView Android
        s.setUserAgentString(s.getUserAgentString() + " XAUUSDAnalystApp/13");

        webView.addJavascriptInterface(new AppInterface(), "AndroidApp");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                // Semua URL dibuka di dalam WebView
                return false;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                swipeRefresh.setRefreshing(false);
            }

            @Override
            public void onReceivedError(WebView view, int errorCode, String desc, String failingUrl) {
                swipeRefresh.setRefreshing(false);
                showConnectionError();
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int progress) {
                if (progress == 100) swipeRefresh.setRefreshing(false);
            }
        });

        // Sembunyikan scrollbar bawaan (UI app punya scrollbar sendiri)
        webView.setScrollBarStyle(View.SCROLLBARS_INSIDE_OVERLAY);
        webView.setHorizontalScrollBarEnabled(false);
    }

    private void setupSwipeRefresh() {
        swipeRefresh.setColorSchemeColors(0xFFF5C842); // gold
        swipeRefresh.setProgressBackgroundColorSchemeColor(0xFF111827);
        swipeRefresh.setOnRefreshListener(() -> {
            webView.reload();
        });
    }

    private void loadUrl(String url) {
        if (!url.startsWith("http")) url = "http://" + url;
        webView.loadUrl(url);
    }

    private String getSavedUrl() {
        return getSharedPreferences("xauusd", MODE_PRIVATE)
                .getString(PREF_KEY_URL, DEFAULT_URL);
    }

    private void saveUrl(String url) {
        getSharedPreferences("xauusd", MODE_PRIVATE)
                .edit().putString(PREF_KEY_URL, url).apply();
    }

    /** Dialog untuk ganti IP server */
    public void showServerDialog() {
        String current = getSavedUrl();
        EditText input = new EditText(this);
        input.setText(current);
        input.setSelectAllOnFocus(true);
        input.setSingleLine(true);
        input.setHint("contoh: http://192.168.1.5:8000");

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int pad = (int)(16 * getResources().getDisplayMetrics().density);
        layout.setPadding(pad, pad, pad, 0);
        layout.addView(input);

        new AlertDialog.Builder(this)
                .setTitle("🖥️ Alamat Server")
                .setMessage("Masukkan IP dan port server XAUUSD kamu:")
                .setView(layout)
                .setPositiveButton("Sambung", (d, w) -> {
                    String url = input.getText().toString().trim();
                    if (!url.isEmpty()) {
                        saveUrl(url);
                        loadUrl(url);
                        Toast.makeText(this, "Menghubungkan ke " + url, Toast.LENGTH_SHORT).show();
                    }
                })
                .setNegativeButton("Batal", null)
                .show();
    }

    private void showConnectionError() {
        new AlertDialog.Builder(this)
                .setTitle("❌ Tidak Bisa Konek")
                .setMessage("Pastikan:\n\n• Server Python sudah jalan\n• HP dan PC di WiFi yang sama\n• IP address benar\n\nMau ubah alamat server?")
                .setPositiveButton("Ubah IP", (d, w) -> showServerDialog())
                .setNegativeButton("Coba Lagi", (d, w) -> webView.reload())
                .show();
    }

    /** JavaScript Interface — dipanggil dari index.html */
    public class AppInterface {
        @JavascriptInterface
        public void changeServer() {
            runOnUiThread(() -> showServerDialog());
        }

        @JavascriptInterface
        public String getServerUrl() {
            return getSavedUrl();
        }

        @JavascriptInterface
        public void showToast(String msg) {
            runOnUiThread(() -> Toast.makeText(MainActivity.this, msg, Toast.LENGTH_SHORT).show());
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        // Tombol Back → navigasi history WebView
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onResume() {
        super.onResume();
        webView.onResume();
    }

    @Override
    protected void onPause() {
        super.onPause();
        webView.onPause();
    }

    @Override
    protected void onDestroy() {
        webView.destroy();
        super.onDestroy();
    }
}
