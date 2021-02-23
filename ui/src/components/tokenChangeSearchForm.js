import formatISO from 'date-fns/formatISO';
import getUnixTime from 'date-fns/getUnixTime';
import parseISO from 'date-fns/parseISO';
import { ErrorMessage, Field, Form, Formik } from 'formik';
import PropTypes from 'prop-types';
import React from 'react';
import DatePicker from 'react-datepicker';
import { useQueryParams, StringParam, withDefault } from 'use-query-params';

import 'react-datepicker/dist/react-datepicker.css';

export default function TokenChangeSearchForm({ onSubmit }) {
  const [query, setQuery] = useQueryParams({
    key: StringParam,
    tokenType: withDefault(StringParam, 'any'),
    ipAddress: StringParam,
    sinceDate: StringParam,
    untilDate: StringParam,
  });

  return (
    <Formik
      initialValues={{
        key: query.key,
        tokenType: query.tokenType,
        ipAddress: query.ipAddress,
        sinceDate: query.sinceDate && parseISO(query.sinceDate),
        untilDate: query.untilDate && parseISO(query.untilDate),
      }}
      validate={(values) => {
        const errors = {};
        if (values.key && values.key.length !== 22) {
          errors.key = 'Invalid token';
        }
        values.search = {};
        if (values.key) values.search.key = values.key;
        if (values.tokenType !== 'any') {
          values.search.token_type = values.tokenType;
        }
        if (values.ipAddress) values.search.ip_address = values.ipAddress;
        if (values.sinceDate) {
          values.search.since = getUnixTime(values.sinceDate);
        }
        if (values.untilDate) {
          values.search.until = getUnixTime(values.untilDate);
        }
        return errors;
      }}
      onSubmit={(values, { setSubmitting }) => {
        onSubmit(values.search);
        const newQuery = { tokenType: values.tokenType };
        if (values.key) newQuery.key = values.key;
        if (values.ipAddress) newQuery.ipAddress = values.ipAddress;
        if (values.sinceDate) newQuery.sinceDate = formatISO(values.sinceDate);
        if (values.untilDate) newQuery.untilDate = formatISO(values.untilDate);
        setQuery(newQuery);
        setSubmitting(false);
      }}
    >
      {({ values, setFieldValue, isSubmitting }) => (
        <Form>
          <label htmlFor="token-key">Token:</label>{' '}
          <Field
            id="token-key"
            name="key"
            type="text"
            maxlength="30"
            placeholder="token"
          />
          <ErrorMessage name="key" component="div" />
          <br />
          <label htmlFor="token-type">Token type:</label>{' '}
          <Field id="token-type" as="select" name="tokenType">
            <option value="any">Any type</option>
            <option value="session">Web sessions</option>
            <option value="user">User tokens</option>
            <option value="notebook">Notebook tokens</option>
            <option value="internal">Internal tokens</option>
          </Field>
          <ErrorMessage name="tokenType" component="div" />
          <br />
          <label htmlFor="ip-address">IP or CIDR block:</label>{' '}
          <Field
            id="ip-address"
            name="ipAddress"
            type="text"
            maxlength="45"
            placeholder="192.0.2.10 or 198.51.100.0/24"
          />
          <ErrorMessage name="ipAddress" component="div" />
          <br />
          <label htmlFor="since">Changes after:</label>{' '}
          <DatePicker
            id="since"
            name="sinceDate"
            dateFormat="yyyy-MM-dd HH:mm"
            showTimeInput
            timeInputLabel="Time:"
            timeFormat="HH:mm"
            selected={values.sinceDate}
            onChange={(date) => setFieldValue('sinceDate', date)}
          />
          <ErrorMessage name="sinceDate" component="div" />
          <br />
          <label htmlFor="until">Changes before:</label>{' '}
          <DatePicker
            id="until"
            name="untilDate"
            dateFormat="yyyy-MM-dd HH:mm"
            showTimeInput
            timeInputLabel="Time:"
            timeFormat="HH:mm"
            selected={values.untilDate}
            onChange={(date) => setFieldValue('untilDate', date)}
          />
          <ErrorMessage name="untilDate" component="div" />
          <button type="submit" disabled={isSubmitting}>
            Search
          </button>
        </Form>
      )}
    </Formik>
  );
}
TokenChangeSearchForm.propTypes = {
  onSubmit: PropTypes.func.isRequired,
};
