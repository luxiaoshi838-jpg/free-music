package com.jianglab.babywife;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.view.View;

/** Centers the user-provided white broom artwork with comfortable button padding. */
final class BroomIconView extends View {
    private final Drawable icon;

    BroomIconView(Context context) {
        super(context);
        icon = context.getResources().getDrawable(R.drawable.broom_clean_icon);
        setClickable(true);
        setFocusable(true);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        if (icon == null) return;
        int side = Math.round(Math.min(getWidth(), getHeight()) * 0.82f);
        int left = (getWidth() - side) / 2;
        int top = (getHeight() - side) / 2;
        icon.setBounds(left, top, left + side, top + side);
        icon.draw(canvas);
    }
}
