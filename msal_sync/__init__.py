 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a/msal_sync/__init__.py b/msal_sync/__init__.py
new file mode 100644
index 0000000000000000000000000000000000000000..958a896c5674d9309996f1d3bfa6716620c26f16
--- /dev/null
+++ b/msal_sync/__init__.py
@@ -0,0 +1 @@
+"""MSAL schedule sync package."""
 
EOF
)
