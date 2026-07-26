package com.jianglab.babywife;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.drawable.GradientDrawable;
import android.view.View;

/** A font-independent, precisely centered back chevron. */
public final class BackChevronView extends View {
    private final Paint chevronPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path chevronPath = new Path();
    private final float density;

    public BackChevronView(Context context) {
        super(context);
        density = getResources().getDisplayMetrics().density;

        GradientDrawable background = new GradientDrawable();
        background.setShape(GradientDrawable.OVAL);
        background.setColor(Color.argb(88, 255, 255, 255));
        setBackground(background);

        chevronPaint.setColor(Color.WHITE);
        chevronPaint.setStyle(Paint.Style.STROKE);
        chevronPaint.setStrokeWidth(2.6f * density);
        chevronPaint.setStrokeCap(Paint.Cap.ROUND);
        chevronPaint.setStrokeJoin(Paint.Join.ROUND);

        setClickable(true);
        setFocusable(true);
        setContentDescription("返回");
        setMinimumWidth(0);
        setMinimumHeight(0);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float centerX = getWidth() / 2f;
        float centerY = getHeight() / 2f;
        float halfHeight = 7.0f * density;
        float leftX = centerX - 4.5f * density;
        float rightX = centerX + 2.5f * density;

        chevronPath.reset();
        chevronPath.moveTo(rightX, centerY - halfHeight);
        chevronPath.lineTo(leftX, centerY);
        chevronPath.lineTo(rightX, centerY + halfHeight);
        canvas.drawPath(chevronPath, chevronPaint);
    }

    @Override
    protected void drawableStateChanged() {
        super.drawableStateChanged();
        setAlpha(isPressed() ? 0.72f : 1.0f);
        invalidate();
    }
}
