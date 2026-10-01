# MittiMitra public landing page

This folder is a static public preview, separate from the Streamlit dashboard
and FastAPI backend. It does not accept farmer details or offer OTP login.

To publish it on Vercel, import the GitHub repository, select `web` as the
project's Root Directory, and use the `Other` framework preset. No build
command or environment variables are needed. Keep the dashboard/API on a
container host with HTTPS, real SMS OTP, persistent storage, and backups before
making farmer accounts publicly accessible.
