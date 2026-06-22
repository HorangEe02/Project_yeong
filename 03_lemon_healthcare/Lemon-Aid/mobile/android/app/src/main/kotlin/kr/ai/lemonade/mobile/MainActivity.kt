package kr.ai.lemonade.mobile

import android.os.Bundle
import android.os.SystemClock
import android.view.View
import android.view.ViewTreeObserver
import io.flutter.embedding.android.FlutterActivity

/**
 * Android entry activity for the Flutter shell.
 *
 * Keeps the native splash visible long enough for the Lemon mascot launch
 * frame to be visible before Flutter renders its first route.
 */
class MainActivity : FlutterActivity() {
    /**
     * Records the native launch timestamp before Flutter starts drawing.
     *
     * @param savedInstanceState optional Android activity state.
     */
    override fun onCreate(savedInstanceState: Bundle?) {
        val launchStartedAt = SystemClock.uptimeMillis()
        super.onCreate(savedInstanceState)
        keepSplashUntilMinimumHold(launchStartedAt)
    }

    /**
     * Delays the first content draw until the minimum splash hold has elapsed.
     *
     * @param launchStartedAt monotonic timestamp captured at activity launch.
     */
    private fun keepSplashUntilMinimumHold(launchStartedAt: Long) {
        val content: View = findViewById(android.R.id.content)
        content.viewTreeObserver.addOnPreDrawListener(
            object : ViewTreeObserver.OnPreDrawListener {
                override fun onPreDraw(): Boolean {
                    val elapsed = SystemClock.uptimeMillis() - launchStartedAt
                    if (elapsed < MINIMUM_SPLASH_HOLD_MILLIS) {
                        return false
                    }
                    if (content.viewTreeObserver.isAlive) {
                        content.viewTreeObserver.removeOnPreDrawListener(this)
                    }
                    return true
                }
            },
        )
    }

    private companion object {
        const val MINIMUM_SPLASH_HOLD_MILLIS = 1200L
    }
}
