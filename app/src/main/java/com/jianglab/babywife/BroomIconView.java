package com.jianglab.babywife;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.view.View;

/** Simple monochrome broom icon that follows the player's white control style. */
final class BroomIconView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path bristles = new Path();

    BroomIconView(Context context) {
        super(context);
        paint.setColor(Color.WHITE);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeCap(Paint.Cap.ROUND);
        paint.setStrokeJoin(Paint.Join.ROUND);
        setClickable(true);
        setFocusable(true);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float w = getWidth();
        float h = getHeight();
        float stroke = Math.max(2f, Math.min(w, h) * 0.065f);
        paint.setStrokeWidth(stroke);

        // Handle.
        canvas.drawLine(w * 0.70f, h * 0.20f, w * 0.44f, h * 0.57f, paint);
        canvas.drawLine(w * 0.65f, h * 0.17f, w * 0.73f, h * 0.23f, paint);

        // Collar.
        canvas.drawLine(w * 0.38f, h * 0.54f, w * 0.49f, h * 0.62f, paint);

        // Minimal fan-shaped broom head.
        bristles.reset();
        bristles.moveTo(w * 0.39f, h * 0.58f);
        bristles.lineTo(w * 0.22f, h * 0.78f);
        bristles.lineTo(w * 0.48f, h * 0.82f);
        bristles.lineTo(w * 0.48f, h * 0.62f);
        canvas.drawPath(bristles, paint);
        canvas.drawLine(w * 0.29f, h * 0.69f, w * 0.31f, h * 0.79f, paint);
        canvas.drawLine(w * 0.37f, h * 0.64f, w * 0.40f, h * 0.80f, paint);
    }
}
