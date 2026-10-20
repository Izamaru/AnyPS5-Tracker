package com.anyps5.tracker;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.Toast;
import java.io.ByteArrayInputStream;
import java.util.Arrays;

/** Apenas conteúdo empacotado no app; os links oficiais abrem no navegador. */
public class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final String HOME = "https://" + HOST + "/assets/index.html";
    private WebView panel;
    private boolean paused;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(16, 20, 18));
        getWindow().setNavigationBarColor(Color.rgb(16, 20, 18));
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.rgb(16, 20, 18));
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                            insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        panel = new WebView(this);
        panel.setBackgroundColor(Color.rgb(16, 20, 18));
        WebSettings settings = panel.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setUserAgentString(settings.getUserAgentString() + " AnyPS5-Tracker-Android/0.2.1");
        panel.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (!HOST.equals(uri.getHost())) return null;
                String name = uri.getLastPathSegment();
                if (!"https".equals(uri.getScheme()) || !"GET".equals(request.getMethod()) ||
                    !Arrays.asList("index.html", "panel.css", "config.js", "controls.js", "mobile.js").contains(name)) {
                    return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", null,
                                                   new ByteArrayInputStream(new byte[0]));
                }
                try {
                    String type = name.endsWith(".html") ? "text/html" : name.endsWith(".css") ? "text/css" : "application/javascript";
                    return new WebResourceResponse(type, "UTF-8", getAssets().open(name));
                } catch (Exception error) {
                    return new WebResourceResponse("text/plain", "UTF-8", new ByteArrayInputStream(new byte[0]));
                }
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("https".equals(uri.getScheme()) && HOST.equals(uri.getHost())) return false;
                if ("https".equals(uri.getScheme())) {
                    try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
                    catch (Exception error) { Toast.makeText(MainActivity.this, "Não foi possível abrir o link.", Toast.LENGTH_SHORT).show(); }
                }
                return true;
            }
        });
        root.addView(panel, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);
        root.requestApplyInsets();
        panel.loadUrl(HOME);
    }

    @Override protected void onPause() {
        paused = true;
        panel.onPause();
        panel.pauseTimers();
        super.onPause();
    }

    @Override protected void onResume() {
        super.onResume();
        if (panel != null) {
            panel.onResume();
            panel.resumeTimers();
            if (paused) panel.evaluateJavascript("if(window.TrackerLastRequestAt && Date.now()-window.TrackerLastRequestAt>60000) location.reload();", null);
        }
        paused = false;
    }

    @Override public void onBackPressed() {
        if (panel.canGoBack()) panel.goBack(); else super.onBackPressed();
    }

    @Override protected void onDestroy() {
        if (panel != null) { panel.stopLoading(); panel.destroy(); }
        super.onDestroy();
    }
}
