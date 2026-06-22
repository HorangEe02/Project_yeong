-- FORCE RLS proof-of-concept. Runs in a THROWAWAY database (rls_poc), never the
-- live lemon DB. Proves the 4 policy archetypes from the rollout design §3.
-- Expected results are asserted with DO blocks that RAISE EXCEPTION on mismatch,
-- so a clean run = all proofs passed.

\set ON_ERROR_STOP on

-- ── non-superuser request role (the precondition for FORCE to matter) ──
DROP ROLE IF EXISTS lemon_app_poc;
CREATE ROLE lemon_app_poc NOLOGIN NOSUPERUSER NOBYPASSRLS;

-- ── Type A: plaintext owner_subject ──
DROP TABLE IF EXISTS a_user_supplements CASCADE;
CREATE TABLE a_user_supplements (id serial primary key, owner_subject text, name text);
INSERT INTO a_user_supplements(owner_subject, name) VALUES
  ('iss::alice', 'alice vit C'), ('iss::bob', 'bob omega3');
ALTER TABLE a_user_supplements ENABLE ROW LEVEL SECURITY;
ALTER TABLE a_user_supplements FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON a_user_supplements TO lemon_app_poc;
GRANT USAGE, SELECT ON SEQUENCE a_user_supplements_id_seq TO lemon_app_poc;
CREATE POLICY owner_rw ON a_user_supplements FOR ALL TO lemon_app_poc
  USING (owner_subject = current_setting('app.current_subject', true))
  WITH CHECK (owner_subject = current_setting('app.current_subject', true));

-- ── Type B: hashed owner_subject_hash ──
DROP TABLE IF EXISTS b_regulated_documents CASCADE;
CREATE TABLE b_regulated_documents (id serial primary key, owner_subject_hash text, doc text);
INSERT INTO b_regulated_documents(owner_subject_hash, doc) VALUES
  (repeat('a',64), 'alice rx'), (repeat('b',64), 'bob rx');
ALTER TABLE b_regulated_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE b_regulated_documents FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON b_regulated_documents TO lemon_app_poc;
CREATE POLICY owner_rw ON b_regulated_documents FOR ALL TO lemon_app_poc
  USING (owner_subject_hash = current_setting('app.current_subject_hash', true))
  WITH CHECK (owner_subject_hash = current_setting('app.current_subject_hash', true));

-- ── Type C: FK child delegating to parent ──
DROP TABLE IF EXISTS c_ingredients CASCADE;
CREATE TABLE c_ingredients (id serial primary key,
  user_supplement_id int references a_user_supplements(id), nutrient text);
INSERT INTO c_ingredients(user_supplement_id, nutrient) VALUES (1,'C'),(2,'EPA');
ALTER TABLE c_ingredients ENABLE ROW LEVEL SECURITY;
ALTER TABLE c_ingredients FORCE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE, DELETE ON c_ingredients TO lemon_app_poc;
CREATE POLICY owner_rw ON c_ingredients FOR ALL TO lemon_app_poc
  USING (EXISTS (SELECT 1 FROM a_user_supplements p
                 WHERE p.id = user_supplement_id
                   AND p.owner_subject = current_setting('app.current_subject', true)));

-- ── Type D: catalog (public read, no per-owner) ──
DROP TABLE IF EXISTS d_products CASCADE;
CREATE TABLE d_products (id serial primary key, product_name text);
INSERT INTO d_products(product_name) VALUES ('Centrum'),('Nature Made');
ALTER TABLE d_products ENABLE ROW LEVEL SECURITY;
ALTER TABLE d_products FORCE ROW LEVEL SECURITY;
GRANT SELECT ON d_products TO lemon_app_poc;
CREATE POLICY catalog_read ON d_products FOR SELECT TO lemon_app_poc USING (true);

-- ═══════════════ PROOFS (as lemon_app_poc, alice context) ═══════════════
SET ROLE lemon_app_poc;
SET app.current_subject = 'iss::alice';
SET app.current_subject_hash = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

DO $$
BEGIN
  -- A1: alice sees only her own row
  IF (SELECT count(*) FROM a_user_supplements) <> 1
     OR (SELECT count(*) FROM a_user_supplements WHERE owner_subject='iss::bob') <> 0 THEN
    RAISE EXCEPTION 'A FAIL: alice should see 1 own row, 0 bob rows';
  END IF;
  -- A2: alice cannot INSERT a row owned by bob (WITH CHECK)
  BEGIN
    INSERT INTO a_user_supplements(owner_subject, name) VALUES ('iss::bob','sneaky');
    RAISE EXCEPTION 'A FAIL: insert as bob should have been blocked';
  EXCEPTION WHEN insufficient_privilege OR check_violation THEN NULL;
  END;
  -- A3: alice CAN insert her own row
  INSERT INTO a_user_supplements(owner_subject, name) VALUES ('iss::alice','alice new');
  -- B: hashed owner isolation
  IF (SELECT count(*) FROM b_regulated_documents) <> 1 THEN
    RAISE EXCEPTION 'B FAIL: alice hash should match exactly 1 row';
  END IF;
  -- C: child visible only when parent is alice-owned (parent id 1=alice, 2=bob)
  IF (SELECT count(*) FROM c_ingredients) <> 1
     OR (SELECT count(*) FROM c_ingredients WHERE user_supplement_id=2) <> 0 THEN
    RAISE EXCEPTION 'C FAIL: only alice-parent child should be visible';
  END IF;
  -- D: catalog fully readable
  IF (SELECT count(*) FROM d_products) <> 2 THEN
    RAISE EXCEPTION 'D FAIL: catalog should be fully readable';
  END IF;
  RAISE NOTICE 'PROOF_ALICE_OK';
END $$;

-- switch to bob context: must see bob's data, never alice's
SET app.current_subject = 'iss::bob';
SET app.current_subject_hash = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';
DO $$
BEGIN
  IF (SELECT count(*) FROM a_user_supplements WHERE owner_subject='iss::alice') <> 0 THEN
    RAISE EXCEPTION 'BOB FAIL: bob must not see alice rows';
  END IF;
  IF (SELECT count(*) FROM a_user_supplements) <> 1 THEN  -- only original bob row
    RAISE EXCEPTION 'BOB FAIL: bob should see exactly his own row(s)';
  END IF;
  RAISE NOTICE 'PROOF_BOB_OK';
END $$;

-- no GUC set: fail-closed (0 rows), proves missing subject != data leak
RESET app.current_subject;
SET app.current_subject_hash = '';
DO $$
BEGIN
  IF (SELECT count(*) FROM a_user_supplements) <> 0 THEN
    RAISE EXCEPTION 'NOGUC FAIL: missing subject must yield 0 rows (fail-closed)';
  END IF;
  IF (SELECT count(*) FROM d_products) <> 2 THEN
    RAISE EXCEPTION 'NOGUC FAIL: catalog read must still work';
  END IF;
  RAISE NOTICE 'PROOF_FAILCLOSED_OK';
END $$;

-- owner (table owner, non-superuser-equivalent path) maintenance: RESET ROLE so
-- we are back to the DB owner; owner is subject to FORCE too, so a maintenance
-- policy or BYPASSRLS/owner-with-policy is needed. Here we prove the design note:
-- the migration/seed path runs as a role that is NOT lemon_app (the real lemon is
-- superuser and bypasses). We emulate by RESET ROLE to the test superuser.
RESET ROLE;
DO $$
BEGIN
  IF (SELECT count(*) FROM a_user_supplements) < 2 THEN
    RAISE EXCEPTION 'OWNER FAIL: superuser/owner maintenance should see all rows';
  END IF;
  RAISE NOTICE 'PROOF_OWNER_OK';
END $$;
