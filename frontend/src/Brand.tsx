// The XpenseC logo, shared by the main page header and the login screen.
function Brand() {
  return (
    <span className="brand">
      <span className="brand__mark" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="#ffffff" strokeWidth="2.6" strokeLinecap="round">
          <path d="M5 5l10 10M15 5L5 15" />
        </svg>
      </span>
      <span>
        Xpense<span className="brand__accent">C</span>
      </span>
    </span>
  )
}

export default Brand
