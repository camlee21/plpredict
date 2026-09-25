import PageHeader from "../components/PageHeader";

export default function PrivacyPolicyPage() {
  return (
    <>
      <PageHeader title="Privacy policy" meta={["Last updated September 2026"]} />
      <main className="page">
        <article className="panel privacy-page">
          <section>
            <h2>What this page covers</h2>
            <p>
              PL Predict is a Premier League score-prediction app. This page explains what
              information we collect when you use it, why, and how it's stored. It applies to
              everyone who visits the site, whether or not you're signed in.
            </p>
          </section>

          <section>
            <h2>Information we collect</h2>
            <p>When you create an account, we collect:</p>
            <ul>
              <li>A username and email address you choose (or, if you sign in with Google, provided by Google - see below).</li>
              <li>Your password, if you register with one - stored as a one-way cryptographic hash, never in plain text.</li>
            </ul>
            <p>When you use the app, we store the data you generate through it:</p>
            <ul>
              <li>Your score predictions for fixtures.</li>
              <li>Leagues you create or join, and your membership/points in them.</li>
            </ul>
          </section>

          <section>
            <h2>Signing in with Google</h2>
            <p>
              If you choose "Sign in with Google," Google shares your name, email address and a
              unique account identifier with us so we can create or log you into your PL Predict
              account. We only request this basic profile information - we never request or
              receive access to your Gmail, Google Drive, contacts, or any other Google data.
            </p>
            <p>
              Accounts created this way don't have a PL Predict password (you sign in through
              Google each time) unless you set one separately.
            </p>
          </section>

          <section>
            <h2>Where your data is stored</h2>
            <p>We rely on a small number of infrastructure providers to run the app:</p>
            <ul>
              <li>Our database (accounts, predictions, leagues) is hosted with Neon (PostgreSQL).</li>
              <li>Our backend server is hosted with Render.</li>
              <li>This website's front-end is hosted with Vercel.</li>
            </ul>
            <p>
              These providers process data only to keep the app running - we don't sell, rent, or
              share your data with anyone else, and we don't use advertising or analytics trackers.
            </p>
          </section>

          <section>
            <h2>What's stored in your browser</h2>
            <p>
              When you log in, your session tokens are stored in your browser's local storage so
              you stay signed in between visits. They're only ever sent to our own backend, never
              to a third party. Signing out clears them from your browser.
            </p>
          </section>

          <section>
            <h2>Your choices</h2>
            <ul>
              <li>You can change your username or password at any time from your Profile page.</li>
              <li>
                You can ask us to delete your account and associated data at any time by contacting
                us (see below) - we don't currently offer a self-service delete button, but we will
                action deletion requests directly.
              </li>
            </ul>
          </section>

          <section>
            <h2>Changes to this policy</h2>
            <p>
              If how we handle data changes meaningfully, we'll update this page and change the
              date above.
            </p>
          </section>

          <section>
            <h2>Contact</h2>
            <p>
              Questions about this policy or your data? Contact us at{" "}
              <a href="mailto:draglashgames@gmail.com">draglashgames@gmail.com</a>.
            </p>
          </section>
        </article>
      </main>
    </>
  );
}
